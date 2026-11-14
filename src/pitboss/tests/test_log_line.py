"""Tests of the ``LOG`` lines: each hand-back and each clean-up, said once (#347)."""

import pathlib
import unittest
from typing import Callable, Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import logline
from . import (
    captured,
    cleanscene,
    cleanworld,
    fakes,
    test_autoclean_world as scenes,
    world,
)

SET_AT = "2030-01-01T01:00:00+00:00"
FREE_AT = "2030-01-01T02:00:00+00:00"
HAND_BACK = (
    "LOG hand-back 2030-01-01T02:00:00+00:00 slot tiny agent agent-1:"
    " returned owner/project#9; head "
)
POSTING = (("sweep", "CONFIG"), ("next", "CONFIG"), ("slots", "next", "CONFIG"))


def slot_steps(
    here: world.World, closing: Sequence[str] = ("free", "tiny", "--done", "agent-1")
) -> None:
    """Put an agent in the slot ``tiny`` on ticket 9, and say it handed back.

    Args:
        here: the world.
        closing: the ``slots`` command that says so: ``free`` by default.
    """
    steps = (
        ("set", "tiny", "agent-1", "#9", "--running", "agent-1", "--now", SET_AT),
        (*closing, "--now", FREE_AT),
    )
    for words in steps:
        world.invoke(here, "slots", words[0], here.config, *words[1:])


def posted(
    here: world.World, words: Sequence[str], kind: str, at: str = FREE_AT
) -> Sequence[str]:
    """The ``LOG`` lines of a kind that a command prints.

    Args:
        here: the world.
        words: the command, with ``CONFIG`` where the configuration goes.
        kind: ``hand-back`` or ``clean-up``.
        at: the time now.

    Returns:
        The lines.
    """
    given = [here.config if each == "CONFIG" else each for each in words]
    out = world.invoke(here, *given, "--now", at).out
    return [line for line in out.splitlines() if line.startswith(f"LOG {kind} ")]


def events_of(here: world.World) -> Sequence[tuple[str, str]]:
    """The recorded events of a world, as who and head.

    Args:
        here: the world.

    Returns:
        A pair for each event.
    """
    found = logline.read(here.ledger.with_suffix(".log"))
    return [(each.who, each.head) for each in found]


def tip_of(path: pathlib.Path) -> str:
    """The commit a worktree is at.

    Args:
        path: the worktree.

    Returns:
        The commit.
    """
    done = captured.run(["git", "-C", str(path), "rev-parse", "HEAD"])
    return done.stdout.strip()


class TestHandBack(unittest.TestCase):
    """A hand-back is a LOG line, with the PR head, printed once."""

    def test_each_command_prints_it_once_without_an_open_pr(self) -> None:
        """``sweep``, ``next`` and ``slots next``: the first prints it, a second not."""
        for words in POSTING:
            here = world.make_world()
            slot_steps(here)
            first = posted(here, words, "hand-back")
            again = [posted(here, each, "hand-back") for each in POSTING]
            assert_that(first, equal_to([HAND_BACK + logline.NO_PR]))
            assert_that(again, equal_to([[]] * len(POSTING)))

    def test_the_head_is_the_one_of_the_pr_that_fixes_the_ticket(self) -> None:
        """An open PR whose body says ``Fixes #9`` gives the head."""
        here = world.make_world()
        pull = {f"{world.PROJECT}/pulls/2": fakes.pull_body(2, body="Fixes #9")}
        here.bodies.update(pull)
        fakes.listed_row(here.bodies, world.PROJECT, 2, body="Fixes #9")
        slot_steps(here)
        found = posted(here, POSTING[0], "hand-back")
        assert_that(found, equal_to([HAND_BACK + fakes.HEAD]))

    def test_the_header_comes_with_the_lines_only(self) -> None:
        """The line that says to post them as they are is printed once."""
        here = world.make_world()
        slot_steps(here)
        words = [here.config, "--now", FREE_AT]
        outs = [world.invoke(here, "next", *words).out for _ in range(2)]
        found = [logline.HEADER in each for each in outs]
        assert_that(found, equal_to([True, False]))

    def test_heard_logs_a_hand_back_once_and_the_agent_stays(self) -> None:
        """``slots heard`` records every hand-back, a notification too (#347)."""
        here = world.make_world()
        slot_steps(here, ("heard", "tiny"))
        first, again = (posted(here, POSTING[0], "hand-back") for _ in range(2))
        found = (first, again, "agent-1" in here.ledger.read_text())
        assert_that(found, equal_to(([HAND_BACK + logline.NO_PR], [], True)))

    def test_a_refused_free_records_nothing(self) -> None:
        """Freeing a slot for the wrong agent is refused and logs no hand-back."""
        here = world.make_world()
        slot_steps(here)
        world.invoke(here, "slots", "free", here.config, "tiny", "--done", "nobody")
        assert_that(len(events_of(here)), equal_to(1))


def sweeping(here: world.World) -> str:
    """The head ``clean`` takes: the tip of the worktree a sweep removes.

    Args:
        here: the world.

    Returns:
        The commit.
    """
    return tip_of(here.workspace / "merged-work")


def containing(dry: str) -> str:
    """The head ``clean-container`` records: the tips of the worktrees it removes.

    Args:
        dry: what its dry run printed.

    Returns:
        The commits, as the log line joins them.
    """
    listed = [pathlib.Path(each) for each in cleanworld.lines_of(dry, "REMOVED PATH")]
    return ", ".join(tip_of(each) for each in listed if (each / ".git").is_file())


Case = tuple[Callable[[], world.World], Sequence[str], Sequence[str]]
CASES: Mapping[str, Case] = {
    "clean": (lambda: scenes.scene("99.9"), ("--dry-run",), ()),
    "clean-worktrees": (world.make_world, (), ("--no-dry-run",)),
    "clean-container": (
        lambda: cleanscene.full_world().here,
        cleanworld.NO_MARKER,
        ("--no-dry-run", *cleanworld.NO_MARKER),
    ),
}


class TestCleanUp(unittest.TestCase):
    """A clean-up is a LOG line, with the heads of the worktrees it removed."""

    def test_sweep_prints_its_clean_up_once(self) -> None:
        """The merged worktree goes; its tip is the head; a second sweep is silent."""
        here = scenes.scene("99.9")
        head = sweeping(here)
        first, later = (
            posted(here, POSTING[0], "clean-up", world.FUTURE) for _ in range(2)
        )
        prefix = "LOG clean-up 2030-01-01T00:00:00+00:00 pitboss sweep: freed "
        found = (len(first), first[0].startswith(prefix), first[0].endswith(head))
        assert_that((found, later), equal_to(((1, True, True), [])))

    def test_each_cleaning_command_logs_its_removal_not_its_dry_run(self) -> None:
        """``clean``, ``clean-worktrees`` and ``clean-container`` record for a sweep."""
        for name, (make, dry, real) in CASES.items():
            here = make()
            listing = scenes.swept(here, name, *dry)
            head = containing(listing) if name.endswith("container") else sweeping(here)
            before = events_of(here)
            scenes.swept(here, name, *real)
            found = (before, events_of(here))
            assert_that(found, equal_to(([], [(f"pitboss {name}", head)])))

    def test_clean_container_records_the_head_only_of_a_worktree_it_removed(
        self,
    ) -> None:
        """A removed worktree's tip is the head; a scratch directory has none."""
        found = []
        for under, name in (("workspace", "merged-work"), ("root", "old")):
            scene = cleanscene.full_world()
            path = (scene.here.workspace if under == "workspace" else scene.root) / name
            head = tip_of(path) if under == "workspace" else logline.NO_WORKTREE
            approved = fakes.directory() / "approved"
            approved.write_text(f"{path}\n")
            args = ("--no-dry-run", "--approved", str(approved), *cleanworld.NO_MARKER)
            scenes.swept(scene.here, "clean-container", *args)
            found.append((events_of(scene.here), [("pitboss clean-container", head)]))
        actual, expected = zip(*found)
        assert_that(actual, equal_to(expected))

    def test_nothing_freed_records_nothing_and_a_bad_count_posts_again(self) -> None:
        """No bytes, no event; a posted file with no number counts as none posted."""
        log = world.make_world().ledger.with_suffix(".log")
        for size in (0, 5):
            freed = logline.Freed(who="pitboss clean", size=size, heads=["x"])
            logline.record_clean(log, freed, world.START)
        logline.beside(log, ".posted").write_text("not a number")
        assert_that((len(logline.read(log)), logline.posted(log)), equal_to((1, 0)))
