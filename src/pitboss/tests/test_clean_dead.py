"""Tests for what is dead and what is live: the checks made on every path."""

import dataclasses
import os
import pathlib
import time
import unittest
from typing import Sequence

from .. import cleanconfig, dead
from . import cleanworld, fakes
from .test_local import CUTOFF, age

FAR = time.time() + 1e6
SEEN = ("marked", "plain")
MARKER = "holds a file named .pitboss-live"
ABOVE = "lies under a directory that holds a .pitboss-live file"
SURE = "is, holds or lies in a live path"


def with_live(
    look: dead.Look, scratch: Sequence[pathlib.Path], live: Sequence[pathlib.Path]
) -> dead.Look:
    """The look, keeping some paths and watching some scratch directories.

    Args:
        look: the look.
        scratch: the scratch directories.
        live: the live paths.

    Returns:
        The new look.
    """
    clean = cleanconfig.Clean(scratch=scratch, live=live, min_free_gib=0)
    return dataclasses.replace(look, clean=clean)


def why(look: dead.Look, path: pathlib.Path) -> str:
    """Why a path is left alone, if nothing in it changed lately.

    Args:
        look: what to keep.
        path: the path.

    Returns:
        The reason, or empty.
    """
    return dead.hold(look, path, FAR)[0]


def reasons(
    look: dead.Look, top: pathlib.Path, names: Sequence[str], cutoff: float = FAR
) -> Sequence[str]:
    """Why each of the named paths below a directory is left alone.

    Args:
        look: what to keep.
        top: the directory.
        names: the names of the paths, relative to it.
        cutoff: what changed after this is in use.

    Returns:
        The reasons, each empty for a path nothing holds.
    """
    return [dead.hold(look, top / name, cutoff)[0] for name in names]


class TestHold(unittest.TestCase):
    """Why a path is left alone."""

    def test_a_marker_in_it_at_any_depth_or_above_it(self) -> None:
        """A directory holding the marker, or lying under one, is live."""
        top = fakes.directory()
        cleanworld.make_directories(
            top, ("marked", "plain", "outer/inner", "group/entry")
        )
        for each in ("marked", "outer/inner", "group"):
            cleanworld.mark_live(top / each)
        look = cleanworld.look_in(top)
        names = ("marked", "plain", "outer", "group/entry")
        cleanworld.same(reasons(look, top, names), [MARKER, "", MARKER, ABOVE])

    def test_the_main_clone_and_the_live_paths(self) -> None:
        """A path that is, holds or lies in one is live."""
        top = fakes.directory()
        live = [top / "holder/cache", top / "locked"]
        cleanworld.put(top, "holder/cache/f", "locked/inner/f", "project/f", "plain/f")
        look = with_live(cleanworld.look_in(top), [], live)
        found = reasons(look, top, ("holder", "locked/inner", "project", "plain"))
        cleanworld.same(found, [SURE, SURE, SURE, ""])

    def test_a_link_is_not_judged_by_what_it_points_at(self) -> None:
        """A link is left alone, whatever it points at."""
        top = fakes.directory()
        cleanworld.make_directories(top, ("target",))
        (top / "link").symlink_to(top / "target")
        cleanworld.same(
            why(cleanworld.look_in(top), top / "link"), "is a symbolic link"
        )

    def test_recent_use(self) -> None:
        """Anything changed after the cutoff is in use, a deep file included."""
        top = fakes.directory()
        cleanworld.put(top, "a/b/c/d/file")
        age(top)
        look = cleanworld.look_in(top)
        before = reasons(look, top, ("a",), CUTOFF)
        cleanworld.put(top, "a/b/c/d/new")
        after = reasons(look, top, ("a",), CUTOFF)
        cleanworld.same((before, after), ([""], ["changed within the idle hours"]))


class TestConsider(unittest.TestCase):
    """A dead path is measured and judged."""

    def test_live_paths_are_not_listed(self) -> None:
        """A marked path is not a candidate; a plain one is, with its size."""
        top = fakes.directory()
        fakes.write(top / "plain/file", "x" * 10000)
        cleanworld.make_directories(top, ("marked",))
        cleanworld.mark_live(top / "marked")
        look = cleanworld.look_in(top)
        seen = {name: dead.consider(look, top / name, "r", FAR) for name in SEEN}
        marked, plain = seen["marked"], seen["plain"]
        cleanworld.same(marked, None)
        cleanworld.same(
            plain and (plain.reason, plain.kept, plain.size > 10000), ("r", "", True)
        )

    def test_work_that_exists_only_here_is_kept(self) -> None:
        """A candidate with an unpushed commit says so."""
        top = fakes.directory()
        cleanworld.make_directories(top, ("clones",))
        clone = fakes.make_repository(top / "clones")
        fakes.commit_file(clone, "only-here")
        kept = dead.consider(cleanworld.look_in(top), clone.parent, "r", FAR)
        cleanworld.same(kept and kept.kept.split(" ")[0], "1")


def listed() -> tuple[dead.Look, pathlib.Path, dead.Candidate]:
    """An entry with a clone in it, listed.

    Returns:
        The look, the clone and the candidate.
    """
    top = fakes.directory()
    cleanworld.put(top, "entry/file")
    clone = fakes.make_repository(top / "entry")
    age(top)
    look = cleanworld.look_in(top)
    made = dead.consider(look, top / "entry", "r", CUTOFF)
    assert made is not None
    return look, clone, made


class TestRecheck(unittest.TestCase):
    """The look just before the removal."""

    def test_nothing_changed(self) -> None:
        """A path as it was listed may go; one that is already gone may."""
        look, _, made = listed()
        gone = dataclasses.replace(made, path=made.path / "gone")
        cleanworld.same(dead.recheck(look, CUTOFF, made), "")
        cleanworld.same(dead.recheck(look, CUTOFF, gone), "")

    def test_a_commit_after_the_listing(self) -> None:
        """Work made since is work that exists only here."""
        look, clone, made = listed()
        fakes.commit_file(clone, "only-here")
        age(made.path)
        cleanworld.same(dead.recheck(look, CUTOFF, made).split(" ")[0], "1")

    def test_a_marker_after_the_listing(self) -> None:
        """A path marked live since is live."""
        look, _, made = listed()
        cleanworld.mark_live(made.path)
        age(made.path)
        cleanworld.same(dead.recheck(look, CUTOFF, made), MARKER)

    def test_an_agent_after_the_listing(self) -> None:
        """A path changed since is in use."""
        look, _, made = listed()
        cleanworld.put(made.path, "agent.log")
        cleanworld.same(
            dead.recheck(look, CUTOFF, made), "changed within the idle hours"
        )


class TestRootFiles(unittest.TestCase):
    """The files a session wrote in the root."""

    def test_root_files_obey_the_same_rules(self) -> None:
        """A file that is live, or in use, or before the hour is not listed."""
        root = cleanworld.session_root("written", "pinned", "recent", "early")
        os.utime(root / "early", (1800, 1800))
        cleanworld.put(root, "recent")
        pinned = with_live(cleanworld.look_in(root), [], [root / "pinned"])
        look = dataclasses.replace(pinned, watch=cleanworld.watching(root))
        found = [each.path.name for each in dead.dead_root_files(look, CUTOFF)]
        elsewhere = dataclasses.replace(look.watch, marker=root / "none")
        absent = dataclasses.replace(look, watch=elsewhere)
        cleanworld.same(
            (found, dead.dead_root_files(absent, CUTOFF)), (["written"], [])
        )


class TestScratch(unittest.TestCase):
    """The entries of the scratch directories."""

    def test_a_dangling_link_does_not_stop_the_look(self) -> None:
        """An entry with a link to nothing is measured as it is."""
        scratch = fakes.directory() / "scratch"
        cleanworld.put(scratch, "entry/file")
        cleanworld.dangle(scratch / "entry/dangling")
        cleanworld.dangle(scratch / "entry-link")
        age(scratch.parent)
        look = with_live(
            cleanworld.look_in(scratch.parent), [scratch, scratch / "none"], []
        )
        found = dead.dead_scratch(look, CUTOFF)
        cleanworld.same(
            [(each.path.name, each.kept) for each in found], [("entry", "")]
        )

    def test_ordering_and_splitting(self) -> None:
        """Largest first, each path once; safe and kept apart."""
        small, big = cleanworld.candidates(pathlib.Path("/"), "a", "b")
        big = dataclasses.replace(big, size=9, kept="why")
        found = dead.ordered([small, big, small])
        cleanworld.same(found, [big, small])
        cleanworld.same((dead.safe(found), dead.unsafe(found)), ([small], [big]))
