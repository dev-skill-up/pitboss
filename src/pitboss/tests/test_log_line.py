"""Tests of the ``LOG`` lines: each hand-back and each clean-up, said once (#347)."""

import datetime
import pathlib
import subprocess
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import logline
from . import cleanruns, cleanscene, fakes, test_autoclean_world as scenes, world

SET_AT = "2030-01-01T01:00:00+00:00"
FREE_AT = "2030-01-01T02:00:00+00:00"
HAND_BACK = (
    "LOG hand-back 2030-01-01T02:00:00+00:00 slot tiny agent agent-1:"
    " returned owner/project#9; head "
)
REMOVING = ("--now", world.FUTURE, "--no-dry-run")


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


def log_lines(out: str, kind: str) -> Sequence[str]:
    """The ``LOG`` lines of one kind in an output.

    Args:
        out: the output.
        kind: ``hand-back`` or ``clean-up``.

    Returns:
        The lines.
    """
    return [line for line in out.splitlines() if line.startswith(f"LOG {kind} ")]


def events_of(here: world.World) -> Sequence[logline.Event]:
    """The events recorded in a world.

    Args:
        here: the world.

    Returns:
        The events.
    """
    return logline.read(here.ledger.with_suffix(".log"))


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

    def test_sweep_prints_the_hand_back_once_with_the_head_of_its_pr(self) -> None:
        """The PR that fixes the ticket gives the head; a second sweep is silent."""
        here = world.make_world()
        branch = {"sha": fakes.HEAD, "ref": "branch-2"}
        here.bodies[f"{world.PROJECT}/pulls/2"] = fakes.pull_body(
            2, body="Fixes #9", head=branch
        )
        slot_steps(here)
        first = world.again(here, "sweep", "--now", FREE_AT).out
        second = world.again(here, "sweep", "--now", FREE_AT).out
        found = (log_lines(first, "hand-back"), log_lines(second, "hand-back"))
        assert_that(found, equal_to(([HAND_BACK + fakes.HEAD], [])))

    def test_a_hand_back_with_no_open_pr_says_so(self) -> None:
        """No open PR fixes the ticket: the head is said to be missing."""
        here = world.make_world()
        slot_steps(here)
        out = world.again(here, "sweep", "--now", FREE_AT).out
        assert_that(log_lines(out, "hand-back"), equal_to([HAND_BACK + logline.NO_PR]))

    def test_slots_next_prints_it_and_then_next_does_not(self) -> None:
        """``slots next`` and ``next`` post the lines not yet posted, once."""
        here = world.make_world()
        slot_steps(here)
        first = world.invoke(here, "slots", "next", here.config, "--now", FREE_AT)
        later = world.again(here, "next", "--now", FREE_AT)
        found = (log_lines(first.out, "hand-back"), log_lines(later.out, "hand-back"))
        assert_that(found, equal_to(([HAND_BACK + logline.NO_PR], [])))

    def test_next_prints_the_hand_back_when_it_comes_first(self) -> None:
        """``next`` with no ticket prints a hand-back that nothing printed yet."""
        here = world.make_world()
        slot_steps(here)
        out = world.again(here, "next", "--now", FREE_AT).out
        assert_that(log_lines(out, "hand-back"), equal_to([HAND_BACK + logline.NO_PR]))

    def test_a_refused_free_records_nothing(self) -> None:
        """Freeing a slot for the wrong agent is refused and logs no hand-back."""
        here = world.make_world()
        slot_steps(here)
        world.invoke(here, "slots", "free", here.config, "tiny", "--done", "nobody")
        assert_that(len(events_of(here)), equal_to(1))


class TestCleanUp(unittest.TestCase):
    """A clean-up is a LOG line, with the heads of the worktrees it removed."""

    def test_sweep_prints_its_clean_up_once(self) -> None:
        """The merged worktree goes; its tip is the head; a second sweep is silent."""
        here = scenes.scene("99.9")
        head = tip_of(here.workspace / "merged-work")
        first = scenes.swept(here, "sweep")
        second = scenes.swept(here, "sweep")
        lines = log_lines(first, "clean-up")
        prefix = "LOG clean-up 2030-01-01T00:00:00+00:00 pitboss sweep: freed "
        found = (len(lines), lines[0].startswith(prefix), lines[0].endswith(head))
        assert_that(found, equal_to((1, True, True)))
        assert_that(log_lines(second, "clean-up"), equal_to([]))

    def test_clean_logs_but_a_dry_run_does_not(self) -> None:
        """``clean`` records its removal for the next sweep; ``--dry-run`` records none."""
        here = scenes.scene("99.9")
        scenes.swept(here, "clean", "--dry-run")
        dry = events_of(here)
        scenes.swept(here, "clean")
        events = events_of(here)
        out = scenes.swept(here, "sweep")
        found = (dry, [each.who for each in events], len(log_lines(out, "clean-up")))
        assert_that(found, equal_to(([], ["pitboss clean"], 1)))

    def test_clean_worktrees_logs_its_removal_and_not_its_dry_run(self) -> None:
        """The head of the removed worktree is its tip."""
        here = world.make_world()
        head = tip_of(here.worktree)
        world.again(here, "clean-worktrees", "--now", world.FUTURE)
        dry = events_of(here)
        world.again(here, "clean-worktrees", *REMOVING)
        found = [(each.who, each.head) for each in events_of(here)]
        assert_that((dry, found), equal_to(([], [("pitboss clean-worktrees", head)])))

    def test_clean_container_logs_its_removal_and_not_its_dry_run(self) -> None:
        """No worktree is named: the line says so."""
        here = cleanscene.full_world().here
        cleanruns.clean(here)
        dry = events_of(here)
        cleanruns.clean(here, "--no-dry-run")
        found = [(each.who, each.head) for each in events_of(here)]
        wanted = [("pitboss clean-container", logline.NO_WORKTREE)]
        assert_that((dry, found), equal_to(([], wanted)))


class TestUnits(unittest.TestCase):
    """The pieces of the log."""

    def test_a_clean_up_that_freed_nothing_has_no_event(self) -> None:
        """Nothing freed, nothing logged; recording nothing writes nothing."""
        here = world.make_world()
        log = here.ledger.with_suffix(".log")
        now = datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)
        logline.record(log, logline.clean_up("pitboss clean", 0, [], now))
        assert_that(logline.events_file(log).exists(), equal_to(False))

    def test_an_unreadable_count_posts_everything_again(self) -> None:
        """A posted file that is not a number counts as none posted."""
        here = world.make_world()
        log = here.ledger.with_suffix(".log")
        now = datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)
        logline.record(log, logline.clean_up("pitboss clean", 5, ["x"], now))
        logline.posted_file(log).write_text("not a number")
        assert_that(logline.posted(log), equal_to(0))
