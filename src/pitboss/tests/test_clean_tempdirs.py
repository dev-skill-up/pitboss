"""``clean-container`` removes idle test tempdirs, counts them, names the used.

A tempdir is ``tmp*`` in a ``[clean] tmp_roots`` directory, owned by the user
running, untouched for ``--tmp-hours`` (2 by default). One that a running
process works in (its current directory, or its ``TMPDIR``) is named and kept
(pitboss#348).
"""

import dataclasses
import pathlib
import subprocess
import sys
import unittest
from typing import Sequence

from .. import dead, machine as machines, procs, tempclean
from . import autocleanworld as fx
from . import cleanruns, cleanworld, fakes, test_local, world

same = cleanworld.same
BUSY = fx.TMP / "tmpbusy"
SLEEP = "import time; time.sleep(60)"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Temps:
    """A world and its tempdir root.

    Attributes:
        here: the world.
        root: the tempdir root. ``tmpold``, ``tmpbusy`` and ``plain-old`` in it
            are 10 hours old, ``tmpyoung`` is new.
    """

    here: world.World
    root: pathlib.Path


def use(here: world.World, root: pathlib.Path) -> None:
    """Make a directory the world's only tempdir root.

    Args:
        here: the world.
        root: the directory.
    """
    settings = f'min_free_gib = 0\ntmp_roots = ["{root}"]\npressure_percent = 100\n'
    cleanworld.rewrite(here, settings)


def temps_of(case: unittest.TestCase) -> Temps:
    """Make a world whose tempdir root holds old, young, busy and other entries.

    A process works in ``tmpbusy/inner``, and is stopped when the test ends.

    Args:
        case: the test.

    Returns:
        The world and its root.
    """
    root = fakes.directory() / "temp"
    cleanworld.put(root, "tmpold/file", "tmpbusy/inner/file", "plain-old/file")
    test_local.age(root)
    cleanworld.put(root, "tmpyoung/file")
    here = world.make_world()
    use(here, root)
    process = subprocess.Popen(
        [sys.executable, "-c", SLEEP], cwd=root / "tmpbusy/inner"
    )
    case.addCleanup(process.wait)
    case.addCleanup(process.kill)
    return Temps(here=here, root=root)


def clean_with_agent(here: world.World, path: pathlib.Path) -> str:
    """Remove for real, one path at a time, with an agent starting in a path.

    Args:
        here: the world.
        path: the file the agent writes just before the first ``rm``.

    Returns:
        What the command printed.
    """
    runner = cleanruns.Starting(inner=here.processes, path=path)
    started = dataclasses.replace(here, processes=runner)
    return cleanruns.clean(started, "--no-dry-run", "--batch", "1").out


class TestTempdirsOfTheCommand(unittest.TestCase):
    """The command removes the idle tempdirs and names the one in use."""

    def test_the_dry_run_counts_them_and_names_the_one_in_use(self) -> None:
        """Only the old one is listed; the young, the busy and the unrelated stay."""
        temps = temps_of(self)
        out = cleanruns.clean(temps.here).out
        same(cleanworld.lines_of(out, "REMOVED PATH"), [f"{temps.root}/tmpold"])
        counted = "clean: 1 test tempdirs untouched for 2 hours, "
        busy = f"clean: kept {temps.root}/tmpbusy "
        used = "(untouched for 2 hours, but a running process works in it)"
        same(cleanworld.absent(out, [counted, busy, used]), [])
        same((temps.root / "tmpold").exists(), True)

    def test_the_real_run_removes_only_the_old_one(self) -> None:
        """The path is FREED; the others are untouched."""
        temps = temps_of(self)
        out = cleanruns.clean(temps.here, "--no-dry-run").out
        same(f"REMOVED PATH {temps.root}/tmpold" in out, True)
        same(out.count(" FREED"), 1)
        names = ("tmpold", "tmpbusy", "tmpyoung", "plain-old")
        there = [(temps.root / name).exists() for name in names]
        same(there, [False, True, True, True])

    def test_the_hours_are_an_argument(self) -> None:
        """At 0 hours the young one is idle too; the busy one is not removed."""
        temps = temps_of(self)
        out = cleanruns.clean(temps.here, "--tmp-hours", "0").out
        removed = cleanworld.lines_of(out, "REMOVED PATH")
        same(removed, [f"{temps.root}/tmpold", f"{temps.root}/tmpyoung"])
        same("clean: 2 test tempdirs untouched for 0 hours, " in out, True)

    def test_a_tempdir_that_changes_after_the_listing_is_left(self) -> None:
        """It is looked at again just before its rm."""
        second = fakes.directory() / "second"
        for name, text in (("tmpbig", "x" * 200_000), ("tmpsmall", "x")):
            fakes.write(second / name / "file", text)
        test_local.age(second)
        here = temps_of(self).here
        use(here, second)
        out = clean_with_agent(here, second / "tmpsmall/agent")
        refused = cleanworld.lines_of(out, "COULD NOT REMOVE PATH")
        same(refused, [f"{second}/tmpsmall"])
        same(
            ((second / "tmpbig").exists(), "changed since it was listed" in out),
            (False, True),
        )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Tmp:
    """A /tmp in memory with two old tempdirs.

    Attributes:
        tree: the tree.
        machine: the machine of no processes that reads it.
    """

    tree: fx.Tree
    machine: machines.Machine


def tmp_of() -> Tmp:
    """Make a /tmp with two old tempdirs and a machine of no processes.

    Returns:
        The tmp.
    """
    tree = fx.Tree()
    fx.put(tree, fx.TMP / "tmpold", 99)
    fx.put(tree, BUSY, 99)
    return Tmp(tree=tree, machine=fx.machine_of(tree))


def split(tmp: Tmp, directory: pathlib.Path) -> tuple[Sequence[str], Sequence[str]]:
    """The names of the tempdirs that may go and of those that are used.

    Args:
        tmp: the tmp.
        directory: where a process works.

    Returns:
        The two lists of names.
    """
    busy = dataclasses.replace(tmp.machine, busy=lambda: {directory})
    free, used = tempclean.split_tempdirs(busy, fx.plain(), 2)
    return fx.names(free), fx.names(used)


class TestSplitting(unittest.TestCase):
    """The tempdirs that may go, and the ones a process works in."""

    def test_a_process_inside_a_tempdir_keeps_it(self) -> None:
        """Its current directory is below the tempdir; the other one may go."""
        tmp = tmp_of()
        same(split(tmp, BUSY / "inner"), (["tmpold"], ["tmpbusy"]))
        stale = tempclean.stale_tempdirs(tmp.machine, fx.plain(), 2)
        same(fx.names(stale), ["tmpbusy", "tmpold"])

    def test_a_tempdir_that_is_a_process_s_directory_is_used(self) -> None:
        """The directory itself counts, not only what is below it."""
        same(split(tmp_of(), BUSY), (["tmpold"], ["tmpbusy"]))

    def test_the_look_before_the_removal(self) -> None:
        """Gone is fine; changed since, or used since, is not; otherwise fine."""
        tmp = tmp_of()
        old = dead.Candidate(path=fx.TMP / "tmpold", size=1, reason="r")
        gone = dataclasses.replace(old, path=fx.TMP / "tmpgone")
        used = dataclasses.replace(tmp.machine, busy=lambda: {old.path})
        cases = [(tmp.machine, old), (tmp.machine, gone), (used, old)]
        said = [tempclean.recheck(machine, 2, each) for machine, each in cases]
        fx.put(tmp.tree, old.path, 0)
        said.append(tempclean.recheck(tmp.machine, 2, old))
        busy = "a running process works in it"
        same(said, ["", "", busy, "changed since it was listed"])


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
        same(sorted(found), [pathlib.Path("/tmp/t1"), pathlib.Path("/work/a")])

    def test_this_process_is_one_of_them(self) -> None:
        """The real ``/proc`` names the directory this test runs in."""
        same(pathlib.Path.cwd() in procs.in_use(), True)
