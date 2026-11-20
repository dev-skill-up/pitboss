"""Tests for what to start next."""

import dataclasses
import json
import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import config, parsing, pulls, reviews, steps, work
from .. import headsignals, rounds, straycomments
from . import fakes, test_flow

REPO = config.make_repo("owner", "project")
GREEN = test_flow.GREEN
SETTINGS = test_flow.SETTINGS
SLOTS = config.Slots(
    ledger=pathlib.Path("/unused"),
    log=pathlib.Path("/unused.log"),
    default=(),
    models=("small", "large"),
    priority_labels=("urgent", "later"),
    model_labels={"hard": "large", "odd": "unknown"},
)
NONE = reviews.Standing.NONE


DEFAULT_STEP = steps.regular_review(steps.Stage.PLAN_AND_EXECUTION)


def stepped(facts: pulls.PullFacts, step: steps.Move) -> pulls.PullFacts:
    """A PR at another step.

    Args:
        facts: the PR.
        step: the step the flow gives it.

    Returns:
        The PR at that step.
    """
    return dataclasses.replace(facts, step=step)


def facts(
    number: int,
    standing: reviews.Standing,
    **changes: object,
) -> pulls.PullFacts:
    """An open, green PR of the project.

    Args:
        number: its number.
        standing: where its head stands.
        **changes: changes to its JSON.

    Returns:
        The PR.
    """
    pull = parsing.pull(json.dumps(fakes.pull_body(number, **changes)))
    return pulls.PullFacts(
        repo=REPO,
        pull=pull,
        checks=(GREEN,),
        review=None,
        standing=standing,
        step=DEFAULT_STEP,
        signals=headsignals.NONE,
        unreadable=straycomments.NONE,
        review_rounds=rounds.NONE,
        relock=False,
    )


def item(
    reference: str,
    category: work.Category,
    priority: int = 0,
    labels: Sequence[str] = (),
) -> work.Item:
    """An item to start.

    Args:
        reference: its reference.
        category: its kind.
        priority: its priority label's index.
        labels: its labels.

    Returns:
        The item.
    """
    return work.Item(
        category=category,
        reference=reference,
        created_at="2026",
        title="t",
        priority=priority,
        labels=frozenset(labels),
    )


Kind = work.Category
REVIEW_STEP = steps.regular_review(steps.Stage.PLAN_AND_EXECUTION)
STEP_CASES: Sequence[tuple[steps.Move, Kind | None]] = [
    (steps.worker(steps.Task.REVISE_PLAN), Kind.REVISE_PLAN),
    (steps.worker(steps.Task.FIX_EXECUTION), Kind.FIX_REVIEW),
    (steps.worker(steps.Task.RULING_STEPS), Kind.RULING_STEPS),
    (steps.worker(steps.Task.RULING_AS_GIVEN), Kind.RULING_AS_GIVEN),
    (steps.worker(steps.Task.FIX_CI), Kind.FIX_CI),
    (steps.worker(steps.Task.FIRST_ROUND), Kind.FIRST_ROUND),
    (steps.worker(steps.Task.RESOLVE_CONFLICT), Kind.RESOLVE_CONFLICT),
    (REVIEW_STEP, Kind.REVIEW),
    (steps.regular_review(steps.Stage.PLAN_ONLY), Kind.REVIEW),
    (steps.merge(), None),
    (steps.undraft(), None),
    (steps.IDLE, None),
    (steps.IDLE, None),
    (steps.IDLE, None),
    (steps.opus_ruling(), None),
    (steps.pause_for_owner(), None),
    (steps.fix_ruling(""), None),
    (steps.ruling_escalates(), None),
]


def _issue(number: int, body: str) -> dict[str, object]:
    return {
        "number": number,
        "title": f"T{number}",
        "created_at": f"2026-10-0{number}",
        "labels": [{"name": "urgent"}],
        "body": body,
    }


ISSUES = [
    _issue(number, body)
    for number, body in [
        (1, ""),
        (2, ""),
        (4, ""),
        (5, "Change `src/thing/` please"),
        (6, "Change `docs/other.md`"),
    ]
]
LISTING = "repos/owner/project/issues?state=open&labels="
TICKET_BODIES = {
    fakes.page(LISTING + "urgent"): ISSUES,
    fakes.page(LISTING + "later"): [ISSUES[4]],
}
NAMING = {
    "title": "Fixes #1",
    "body": (
        "Fixes https://github.com/owner/project/issues/2\nCloses lib#3\nFixes soon\n"
        "## Plan\nsee #5 and https://github.com/owner/project/issues/6"
    ),
    "head": {"sha": fakes.HEAD, "ref": "claude/work-4"},
}


class TestTickets(unittest.TestCase):
    """Open tickets that no open PR names."""


class TestOrderAndAssign(unittest.TestCase):
    """Sorting and filling empty slots."""

    def test_smallest_model(self) -> None:
        """Labels raise the floor; failures move up; all failed is none."""
        hard = item("h", work.Category.NEW_PR, labels=["hard", "odd"])
        plain = item("p", work.Category.NEW_PR)
        found = [
            work.smallest_model(hard, SLOTS, {}),
            work.smallest_model(plain, SLOTS, {"p": ["small"]}),
            work.smallest_model(plain, SLOTS, {"p": ["small", "large"]}),
        ]
        assert_that(found, equal_to(["large", "large", None]))
