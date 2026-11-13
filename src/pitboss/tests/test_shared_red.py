"""Tests for a check red on several PRs from one cause (keyword: shared-red)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import sharedred
from . import fakes, quietworld, world
from .test_commands import sweep
from .test_slot_commands import next_output

PROJECT = world.PROJECT
CAUSE = "pin 107 commits stale"
OTHER = "lockfile out of date"
SHARED = "SHARED RED owner/project:"
TICKET = "file one ticket for the red check the PRs share"
FIX = ": fix CI on the head"
PAGE = fakes.page(f"{PROJECT}/pulls?state=open")


def failed(identifier: int, head: str) -> Mapping[str, object]:
    """A failed check run named ``canonical-files``.

    Args:
        identifier: its id.
        head: the commit it ran on.

    Returns:
        The check run's JSON.
    """
    return {
        "id": identifier,
        "name": "canonical-files",
        "status": "completed",
        "conclusion": "failure",
        "head_sha": head,
        "started_at": "2026-10-01T09:50:00Z",
        "completed_at": "2026-10-01T10:00:00Z",
    }


def explain(here: world.World, identifier: int, line: str) -> None:
    """Make a failed check say why it failed.

    Args:
        here: the world.
        identifier: the check run's id.
        line: its output title.
    """
    here.bodies[f"{PROJECT}/check-runs/{identifier}"] = {
        "output": {"title": line, "summary": ""}
    }


def put_pull(here: world.World, number: int, line: str) -> None:
    """Add (or replace) an open PR whose check fails with a line.

    Args:
        here: the world.
        number: the PR's number; its check run's id is ten times that.
        line: the error line of its failed check.
    """
    here.bodies.update(
        world.pull_bodies(
            "owner/project", number, [failed(number * 10, str(number) * 40)], "behind"
        )
    )
    open_ones = here.bodies[PAGE]
    listed = {each["number"] for each in open_ones}  # type: ignore[attr-defined]
    here.bodies[PAGE] = [{"number": each} for each in sorted(listed | {number})]
    explain(here, number * 10, line)


def shared_world(causes: Mapping[int, str], main: str | None = None) -> world.World:
    """A world with a red PR for each number, each with its own cause.

    Args:
        causes: the PR numbers (3 and up) and the error line of each.
        main: the error line of main's failed check, or None when main passes.

    Returns:
        The world.
    """
    here = world.make_world()
    for number, line in causes.items():
        put_pull(here, number, line)
    if main:
        here.bodies[fakes.page(f"{PROJECT}/commits/main/check-runs")] = {
            "check_runs": [failed(99, "9" * 40)]
        }
        explain(here, 99, main)
    return quietworld.unheld(here)


def said(here: world.World) -> Sequence[str]:
    """The SHARED RED lines of a sweep.

    Args:
        here: the world.

    Returns:
        The lines.
    """
    return [line for line in sweep(here).out.splitlines() if SHARED in line]


def offers(text: str, word: str) -> Sequence[str]:
    """The NEXT lines of ``slots next`` that hold a word.

    Args:
        text: its output.
        word: the word.

    Returns:
        The lines.
    """
    return [
        each for each in text.splitlines() if each.startswith("NEXT") and word in each
    ]


class TestGroups(unittest.TestCase):
    """The check, the PRs and the line are one finding."""

    def test_c20_three_prs_with_one_cause_are_reported_once(self) -> None:
        """One line names the check, all three PRs and the first error line."""
        found = said(shared_world({3: CAUSE, 5: CAUSE, 6: CAUSE}))
        words = ["canonical-files", CAUSE, *[f"owner/project#{n}" for n in (3, 5, 6)]]
        assert_that(
            [len(found), [w in found[0] for w in words]],
            equal_to([1, [True] * len(words)]),
        )

    def test_c20_slots_next_offers_one_ticket_and_no_fix(self) -> None:
        """The lowest PR files the ticket, the others wait, nobody fixes."""
        text = next_output(shared_world({3: CAUSE, 5: CAUSE, 6: CAUSE}))
        fixes = [f"owner/project#{n} {FIX}" for n in (3, 5, 6)]
        assert_that(
            [len(offers(text, TICKET)), "SHARED RED line" in text, "UNKNOWN" in text]
            + [word in text for word in fixes],
            equal_to([1, True, False, False, False, False]),
        )

    def test_c20_different_causes_are_not_shared(self) -> None:
        """Two PRs failing the same check for different lines are fixed each."""
        here = shared_world({3: CAUSE, 5: OTHER})
        text = next_output(here)
        assert_that(
            [said(here), f"owner/project#3 {FIX}" in text, TICKET in text],
            equal_to([[], True, False]),
        )

    def test_c20_main_red_and_a_pr_red_are_one_finding(self) -> None:
        """A check red on main with the PR's line is shared with main."""
        found = said(shared_world({3: CAUSE}, main=CAUSE))
        assert_that(len(found), equal_to(1))
        assert_that(found[0], contains_string("main, owner/project#3"))

    def test_c20_main_red_for_another_cause_is_not_shared(self) -> None:
        """Main's failed check with another line is not the PR's cause."""
        assert_that(said(shared_world({3: CAUSE}, main=OTHER)), equal_to([]))


class TestUnits(unittest.TestCase):
    """The grouping alone."""

    def test_c20_no_line_and_two_repositories_share_nothing(self) -> None:
        """Two holders with an empty line, or in two repositories, are no group."""
        empty = [("o/r", f"o/r#{n}", "") for n in (1, 2)]
        apart = [(f"o/{r}", f"o/{r}#1", "x") for r in ("a", "b")]
        for each in (empty, apart):
            seen = [
                sharedred.Seen(slug=slug, holder=holder, check="c", line=line)
                for slug, holder, line in each
            ]
            assert_that(sharedred.groups(seen), equal_to([]))
