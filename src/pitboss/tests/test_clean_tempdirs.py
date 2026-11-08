"""``clean-container`` removes idle test tempdirs, counts them, names the used (pitboss#348).

A tempdir is ``tmp*`` in a ``[clean] tmp_roots`` directory, owned by the user
running, untouched for ``--tmp-hours`` (2 by default). One that a running
process works in (its current directory, or its ``TMPDIR``) is named and kept.
"""

import dataclasses
import pathlib
import subprocess
import sys
import unittest

from .. import dead, procs, tempclean
from . import autocleanworld as fx
from . import cleanruns, cleanworld, fakes, test_local, world

same = cleanworld.same
BUSY = fx.TMP / "tmpbusy"


def tempdir_world() -> tuple[world.World, pathlib.Path]:
    """A world whose tempdir root holds old, young, busy and unrelated entries.

    Returns:
        The world and the root. ``tmpold``, ``tmpbusy`` and ``plain-old`` are
        10 hours old, ``tmpyoung`` is new.
    """
    here = world.make_world()
    root = fakes.directory() / "temp"
    for name in ("tmpold", "tmpbusy/inner", "plain-old"):
        fakes.write(root / name / "file", name)
    test_local.age(root)
    fakes.write(root / "tmpyoung" / "file", "new")
    settings = f'min_free_gib = 0\ntmp_roots = ["{root}"]\npressure_percent = 100\n'
    cleanworld.rewrite(here, settings)
    return here, root


def worker_in(directory: pathlib.Path) -> subprocess.Popen[bytes]:
    """A running process whose current directory is a directory.

    Args:
        directory: the directory.

    Returns:
        The process, which is stopped when the test ends.
    """
    code = "import time; time.sleep(60)"
    return subprocess.Popen([sys.executable, "-c", code], cwd=directory)


class TestTempdirsOfTheCommand(unittest.TestCase):
    """The command removes the idle tempdirs and names the one in use."""

    def worker(self, directory: pathlib.Path) -> None:
        """Start a process in a directory, to be stopped when the test ends.

        Args:
            directory: the directory.
        """
        process = worker_in(directory)
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)

    def test_the_dry_run_counts_them_and_names_the_one_in_use(self) -> None:
        """Only the old one is listed; the young, the busy and the unrelated stay."""
        here, root = tempdir_world()
        self.worker(root / "tmpbusy" / "inner")
        out = cleanruns.clean(here).out
        same(cleanworld.lines_of(out, "REMOVED PATH"), [f"{root}/tmpold"])
        counted = "clean: 1 test tempdirs untouched for 2 hours, "
        busy = f"clean: kept {root}/tmpbusy "
        used = "(untouched for 2 hours, but a running process works in it)"
        same(cleanworld.absent(out, [counted, busy, used]), [])
        same(all((root / name).exists() for name in ("tmpold", "tmpbusy")), True)

    def test_the_real_run_removes_only_the_old_one(self) -> None:
        """The path is FREED; the others are untouched."""
        here, root = tempdir_world()
        self.worker(root / "tmpbusy" / "inner")
        out = cleanruns.clean(here, "--no-dry-run").out
        same(f"REMOVED PATH {root}/tmpold" in out, True)
        same(out.count(" FREED"), 1)
        kept = [(root / name).exists() for name in ("tmpbusy", "tmpyoung", "plain-old")]
        same([(root / "tmpold").exists(), *kept], [False, True, True, True])

    def test_the_hours_are_an_argument(self) -> None:
        """At 0 hours the young one is idle too; the busy one is not removed."""
        here, root = tempdir_world()
        self.worker(root / "tmpbusy" / "inner")
        out = cleanruns.clean(here, "--tmp-hours", "0").out
        same(
            cleanworld.lines_of(out, "REMOVED PATH"),
            [f"{root}/tmpold", f"{root}/tmpyoung"],
        )
        same("clean: 2 test tempdirs untouched for 0 hours, " in out, True)

    def test_a_tempdir_that_changes_after_the_listing_is_left(self) -> None:
        """It is looked at again just before its rm."""
        here = tempdir_world()[0]
        root = fakes.directory() / "second"
        fakes.write(root / "tmpbig" / "file", "x" * 200_000)
        fakes.write(root / "tmpsmall" / "file", "x")
        test_local.age(root)
        cleanworld.rewrite(
            here,
            f'min_free_gib = 0\ntmp_roots = ["{root}"]\npressure_percent = 100\n',
        )
        runner = cleanruns.Starting(inner=here.processes, path=root / "tmpsmall/agent")
        out = cleanruns.clean(
            dataclasses.replace(here, processes=runner), "--no-dry-run", "--batch", "1"
        ).out
        refused = cleanworld.lines_of(out, "COULD NOT REMOVE PATH")
        same(refused, [f"{root}/tmpsmall"])
        same((root / "tmpbig").exists(), False)
        same("changed since it was listed" in out, True)


def tempdir_tree() -> fx.Tree:
    """A /tmp with two old tempdirs, one of which a process works in.

    Returns:
        The tree.
    """
    tree = fx.Tree()
    fx.put(tree, fx.TMP / "tmpold", 99)
    fx.put(tree, BUSY, 99)
    return tree


class TestSplitting(unittest.TestCase):
    """The tempdirs that may go, and the ones a process works in."""

    def test_a_process_inside_a_tempdir_keeps_it(self) -> None:
        """Its current directory is below the tempdir; the other one may go."""
        machine = dataclasses.replace(
            fx.machine_of(tempdir_tree()), busy=lambda: {BUSY / "inner"}
        )
        free, used = tempclean.split_tempdirs(machine, fx.plain(), 2)
        same((fx.names(free), fx.names(used)), (["tmpold"], ["tmpbusy"]))
        same(fx.names(tempclean.stale_tempdirs(machine, fx.plain(), 2)), ["tmpold"])

    def test_a_tempdir_that_is_a_process_s_directory_is_used(self) -> None:
        """The directory itself counts, not only what is below it."""
        machine = dataclasses.replace(
            fx.machine_of(tempdir_tree()), busy=lambda: {BUSY}
        )
        same(fx.names(tempclean.split_tempdirs(machine, fx.plain(), 2)[1]), ["tmpbusy"])

    def test_the_look_before_the_removal(self) -> None:
        """Gone is fine; changed since, or used since, is not; otherwise fine."""
        tree = tempdir_tree()
        old = dead.Candidate(path=fx.TMP / "tmpold", size=1, reason="r")
        gone = dead.Candidate(path=fx.TMP / "tmpgone", size=1, reason="r")
        plain = fx.machine_of(tree)
        used = dataclasses.replace(plain, busy=lambda: {old.path})
        same(tempclean.recheck(plain, 2, old), "")
        same(tempclean.recheck(plain, 2, gone), "")
        same(tempclean.recheck(used, 2, old), "a running process works in it")
        fx.put(tree, old.path, 0)
        same(tempclean.recheck(plain, 2, old), "changed since it was listed")


class TestProcesses(unittest.TestCase):
    """The directories the running processes work in."""

    def test_a_process_works_in_its_directory_and_its_tmpdir(self) -> None:
        """The ones that cannot be read, and what is no process, count for nothing."""
        proc = fakes.directory() / "proc"
        (proc / "11").mkdir(parents=True)
        (proc / "11/cwd").symlink_to("/work/a")
        (proc / "11/environ").write_bytes(b"A=1\0TMPDIR=/tmp/t1\0B=2")
        (proc / "22").mkdir()
        (proc / "self").mkdir()
        (proc / "stat").write_text("x")
        found = procs.in_use(proc)
        same(found, {pathlib.Path("/work/a"), pathlib.Path("/tmp/t1")})

    def test_this_process_is_one_of_them(self) -> None:
        """The real ``/proc`` names the directory this test runs in."""
        same(pathlib.Path.cwd() in procs.in_use(), True)
