"""``pitboss push`` refuses a tree no green ``pitboss nox`` ran on (pitboss#471)."""

import datetime
import pathlib
import unittest
from typing import Sequence

from .. import noxcheck, noxgreen
from . import fakes, world
from .cleanworld import same

WHEN = "2030-01-01T00:00:00+00:00"
SESSIONS = [each.value for each in noxcheck.WITHOUT_TESTS]
BRANCH = ["branch-1"]


def record(top: pathlib.Path, tree: str, sessions: Sequence[str]) -> None:
    """Record a green run of a tree.

    Args:
        top: the git directory.
        tree: the tree hash.
        sessions: the sessions that ran.
    """
    noxgreen.record(noxgreen.Place(head="h", path=top / "x", tree=tree), WHEN, sessions)


def push(here: world.World) -> world.Result:
    """Push the branch of a world at minute 1.

    Args:
        here: the world.

    Returns:
        What the push did.
    """
    fakes.run_git(here.clone, "branch", "-f", *BRANCH)
    later = (world.START + datetime.timedelta(minutes=1)).isoformat()
    argv = ["push", here.config, "--now", later, "--no-dry-run", "--draft"]
    return world.invoke(here, *argv, "origin", *BRANCH, directory=here.clone)


def pushing(here: world.World) -> world.Result:
    """Push the branch of a world whose clone has a ``noxfile.py``.

    Args:
        here: the world.

    Returns:
        What the push did.
    """
    (here.clone / "noxfile.py").write_text("", encoding="utf-8")
    return push(here)


def facts(here: world.World) -> tuple[str, pathlib.Path]:
    """The tree and git directory of a world's clone.

    Args:
        here: the world.

    Returns:
        The tree hash and the git directory.
    """
    asked = ("HEAD^{tree}", "--absolute-git-dir")
    tree, top = [fakes.run_git(here.clone, "rev-parse", each).strip() for each in asked]
    return tree, pathlib.Path(top)


class TestRecord(unittest.TestCase):
    """A green run records its tree with the sessions that ran."""

    def test_what_is_read_back_is_what_was_recorded_for_that_tree(self) -> None:
        """The same tree, another tree, a directory with no file, a file not text."""
        top = fakes.directory()
        record(top, "t1", SESSIONS)
        unreadable = fakes.directory()
        (unreadable / noxgreen.TREE_RECORD).write_bytes(b"\xff\xfe")
        found = [
            noxgreen.ran_green(top, "t1"),
            noxgreen.ran_green(top, "t2"),
            noxgreen.ran_green(top / "none", "t1"),
            noxgreen.ran_green(unreadable, "t1"),
        ]
        same(found, [frozenset(SESSIONS), frozenset(), frozenset(), frozenset()])


class TestPush(unittest.TestCase):
    """The push needs the result of the exact tree."""

    def test_each_tree_is_judged_by_its_own_result(self) -> None:
        """None, another tree's, part of the sessions, all of them, no noxfile."""
        here = world.make_world()
        tree, top = facts(here)
        none = pushing(here)
        record(top, "other", SESSIONS)
        other = pushing(here)
        record(top, tree, SESSIONS[:2])
        part = pushing(here)
        record(top, tree, SESSIONS)
        full = pushing(here)
        missing = f"missing sessions: {', '.join(SESSIONS)}; run `pitboss nox` on this"
        refused = f"push REFUSED: no green `pitboss nox` is recorded for tree {tree}; "
        same([each.code for each in (none, other, part, full)], [1, 1, 1, 0])
        same(none.out.startswith(refused + missing), True)
        same(other.out.startswith(refused + missing), True)
        same(f"missing sessions: {SESSIONS[2]}; run" in part.out, True)
        same(full.out, "pushed\n")

    def test_a_repository_without_a_noxfile_is_not_asked(self) -> None:
        """The check is for a repository that has the sessions."""
        done = push(world.make_world())
        same((done.code, done.out), (0, "pushed\n"))
