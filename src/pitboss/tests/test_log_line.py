"""Tests of the ``LOG`` lines: each hand-back and each clean-up, said once (#347)."""

import pathlib
import subprocess
import unittest
from typing import Callable, Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import logline
from . import cleanscene, cleanworld, fakes, test_autoclean_world as scenes, world

SET_AT = "2030-01-01T01:00:00+00:00"
FREE_AT = "2030-01-01T02:00:00+00:00"
HAND_BACK = (
    "LOG hand-back 2030-01-01T02:00:00+00:00 slot tiny agent agent-1:"
    " returned owner/project#9; head "
)
POSTING = (("sweep", "CONFIG"), ("next", "CONFIG"), ("slots", "next", "CONFIG"))


def slot_steps(here: world.World) -> None:
    """Put an agent in the slot ``tiny`` on ticket 9, and free it as handed back.

    Args:
        here: the world.
    """
    steps = (
        ("set", "tiny", "agent-1", "#9", "--running", "agent-1", "--now", SET_AT),
        ("free", "tiny", "--done", "agent-1", "--now", FREE_AT),
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
    done = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
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
        slot_steps(here)
        found = posted(here, POSTING[0], "hand-back")
        assert_that(found, equal_to([HAND_BACK + fakes.HEAD]))

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
            head = logline.NO_WORKTREE if name.endswith("container") else sweeping(here)
            scenes.swept(here, name, *dry)
            before = events_of(here)
            scenes.swept(here, name, *real)
            found = (before, events_of(here))
            assert_that(found, equal_to(([], [(f"pitboss {name}", head)])))

    def test_nothing_freed_records_nothing_and_a_bad_count_posts_again(self) -> None:
        """No bytes, no event; a posted file with no number counts as none posted."""
        log = world.make_world().ledger.with_suffix(".log")
        for size in (0, 5):
            freed = logline.Freed(who="pitboss clean", size=size, heads=["x"])
            logline.record_clean(log, freed, world.START)
        logline.beside(log, ".posted").write_text("not a number")
        assert_that((len(logline.read(log)), logline.posted(log)), equal_to((1, 0)))
