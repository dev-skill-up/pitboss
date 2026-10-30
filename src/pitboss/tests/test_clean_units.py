"""Tests for the pieces of cleaning: sizes, safety, liveness, free space, settings."""

import argparse
import contextlib
import dataclasses
import io
import pathlib
import unittest
from typing import Mapping

from hamcrest import assert_that, contains_string, greater_than

from .. import cleaning, cleanconfig, dead, deadscan, disk
from . import fakes
from .cleanworld import failing, look_in, make_directories, mark_live, same, touch_now
from .test_local import CUTOFF, age


def tree() -> pathlib.Path:
    """A directory with a nested checkout three levels down and one four down.

    Returns:
        The directory.
    """
    top = fakes.directory()
    fakes.run_git(top, "init", "-q")
    fakes.write(top / "a" / "file", "x" * 10000)
    for deep in ("a/b/c", "a/b/c/d"):
        (top / deep).mkdir(parents=True, exist_ok=True)
        fakes.run_git(top / deep, "init", "-q")
    (top / "node_modules" / "x" / ".git").mkdir(parents=True)
    return top


class TestSizesAndRoots(unittest.TestCase):
    """What a tree holds, and where its checkouts are."""

    def test_tree_size(self) -> None:
        """A tree holds at least its file's bytes; a gone path holds none."""
        top = tree()
        found = (dead.tree_size(top) > 10000, dead.tree_size(top / "missing"))
        same(found, (True, 0))

    def test_git_roots(self) -> None:
        """Checkouts three levels down count, deeper ones and node_modules do not."""
        top = tree()
        names = [str(each.relative_to(top)) for each in dead.git_roots(top)]
        same(sorted(names), [".", "a/b/c"])

    def test_touched(self) -> None:
        """A file and a directory are touched when newer than the cutoff."""
        top = fakes.directory()
        target = top / "d" / "f"
        fakes.write(target, "x")
        age(top)
        found = [dead.touched(top, CUTOFF)]
        touch_now(target)
        found += map(lambda each: dead.touched(each, CUTOFF), (target, top))
        same(found, [False, True, True])


class TestTrouble(unittest.TestCase):
    """Why a path is not safe."""

    def test_trouble(self) -> None:
        """Unpushed commits, tracked changes and a broken repository each say so."""
        clone = fakes.make_repository(fakes.directory())
        run = fakes.FakeProcesses(bodies={})
        clean = dead.trouble(run, clone)
        (clone / "untracked").write_text("x")
        untracked = dead.trouble(run, clone)
        (clone / "README").write_text("changed")
        changed = dead.trouble(run, clone)
        fakes.run_git(clone, "checkout", "-q", "--", "README")
        fakes.commit_file(clone, "new")
        ahead = dead.trouble(run, clone)
        broken = fakes.directory()
        (broken / ".git").mkdir()
        mute = dead.trouble(failing, clone)
        found = (clean, untracked, changed, ahead, dead.trouble(run, broken))
        same(mute, f"git cannot read {clone}")
        expected = (
            "",
            "",
            f"1 changed tracked files in {clone}",
            f"1 commits on no remote branch in {clone}",
            f"git cannot read {broken}",
        )
        same(found, expected)


class TestLive(unittest.TestCase):
    """What is marked live."""

    def test_is_live(self) -> None:
        """The marker, a live path, what holds or lies in one, and the main clone."""
        top = fakes.directory()
        folders = ("marked", "plain", "holder", "locked/inner", "project")
        make_directories(top, (*folders, "holder/cache"))
        mark_live(top / "marked")
        live = [top / "holder" / "cache", top / "locked"]
        clean = cleanconfig.Clean(scratch=[], live=live, min_free_gib=0)
        here = dataclasses.replace(look_in(top), clean=clean)
        found = list(map(lambda each: dead.is_live(top / each, here), folders))
        same(found, [True, False, True, True, True])


class TestSlug(unittest.TestCase):
    """The repository a remote URL names."""

    def test_slug_of(self) -> None:
        """Forms with an owner give it; a bare path gives nothing."""
        urls = [
            "https://github.com/o/r.git\n",
            "git@github.com:o/r",
            "/nowhere",
            "x.git",
        ]
        same([deadscan.slug_of(url) for url in urls], ["o/r", "o/r", "", ""])


class TestDisk(unittest.TestCase):
    """Free space."""

    def test_low_space(self) -> None:
        """A filesystem is named once, only when low; a missing path is left out."""
        here = fakes.directory()
        (here / "b").mkdir()

        def small(path: pathlib.Path) -> int:
            return 2**30

        names = [here, here / "b", here / "missing"]
        low = [each.path for each in disk.low_space(names, 2.0, small)]
        same((low, disk.low_space(names, 0.5, small)), ([here], []))
        same(disk.low_space(names, 0, small), [])
        assert_that(disk.free_space(here), greater_than(0))

    def test_size_text(self) -> None:
        """Sizes are in MiB under a GiB, else GiB."""
        sizes = {3 * 2**20: "3.0 MiB", 3 * 2**30: "3.0 GiB"}
        same({size: disk.size_text(size) for size in sizes}, sizes)


def message(document: Mapping[str, object]) -> str:
    """The error the settings of a document raise.

    Args:
        document: the document.

    Returns:
        The message.
    """
    return fakes.error_of(lambda: cleanconfig.from_document(document))


class TestSettings(unittest.TestCase):
    """The ``[clean]`` table."""

    def test_defaults_and_values(self) -> None:
        """An absent table is empty with the default minimum."""
        absent = cleanconfig.from_document({})
        table = {"scratch": ["/a"], "live": ["/b"], "min_free_gib": 2}
        given = cleanconfig.from_document({"clean": table})
        found = (absent.scratch, absent.min_free_gib, given.scratch, given.live)
        same(found, ((), 5.0, (pathlib.Path("/a"),), (pathlib.Path("/b"),)))

    def test_errors(self) -> None:
        """A table, a list and a non-negative minimum are required."""
        bad: list[Mapping[str, object]] = [
            {"clean": 3},
            {"clean": {"scratch": "/a"}},
            {"clean": {"min_free_gib": -1}},
        ]
        found = [message(document) for document in bad]
        for text, expected in zip(found, ("a table", "a list", "negative")):
            assert_that(text, contains_string(expected))


def refused(text: str) -> bool:
    """Whether the parser's count type refuses a word.

    Args:
        text: the word.

    Returns:
        True when it does.
    """
    try:
        cleaning.positive(text)
    except argparse.ArgumentTypeError:
        return True
    return False


class TestCommandPieces(unittest.TestCase):
    """The arguments and the removal in parts."""

    def test_positive(self) -> None:
        """A count above 0 is read; 0 and words are refused."""
        same(cleaning.positive("3"), 3)
        same([refused("0"), refused("x"), refused("3")], [True, True, False])

    def test_read_approved(self) -> None:
        """Comments and blank lines are skipped; no file is no list."""
        listing = fakes.directory() / "approved"
        listing.write_text("# a\n\n/x/y\n /z \n")
        same(
            cleaning.read_approved(str(listing)),
            {pathlib.Path("/x/y"), pathlib.Path("/z")},
        )
        same(cleaning.read_approved(None), None)

    def test_removals_in_parts(self) -> None:
        """A failed rm leaves the paths there, and each call has at most batch paths."""
        here = fakes.directory()
        found = [dead.Candidate(path=here / name, size=0, reason="r") for name in "abc"]
        for each in found:
            each.path.mkdir()
        stuck = [gone for _, gone in cleaning.removals(failing, found, 2, False)]
        run = fakes.FakeProcesses(bodies={})
        done = [gone for _, gone in cleaning.removals(run, found, 2, False)]
        calls = [len(call) - 3 for call in run.calls]
        left = [each.path.exists() for each in found]
        same((stuck, done, calls, left), ([False] * 3, [True] * 3, [2, 1], [False] * 3))

    def test_a_path_that_stays_is_said(self) -> None:
        """A path that rm left is a COULD NOT REMOVE PATH line, not a removal."""
        here = fakes.directory()
        found = [dead.Candidate(path=here / "stay", size=0, reason="r")]
        (here / "stay").mkdir()
        args = argparse.Namespace(no_dry_run=True, run=failing, batch=2)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            gone = cleaning.remove_all(args, found)
        same((gone, out.getvalue().startswith("COULD NOT REMOVE PATH")), ([], True))
