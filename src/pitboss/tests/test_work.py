"""Tests for what to start next."""

import dataclasses
import json
import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import config, ledger, parsing, pulls, reviews, steps, work
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


def stepped(facts: pulls.PullFacts, step: steps.Next) -> pulls.PullFacts:
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
STEP_CASES: Sequence[tuple[steps.Next, Kind | None]] = [
    (steps.worker(steps.Task.REVISE_PLAN), Kind.REVISE_PLAN),
    (steps.worker(steps.Task.FIX_EXECUTION), Kind.FIX_REVIEW),
    (steps.worker(steps.Task.RULING_STEPS), Kind.FIX_REVIEW),
    (steps.worker(steps.Task.RULING_AS_GIVEN), Kind.FIX_REVIEW),
    (steps.worker(steps.Task.FIX_CI), Kind.FIX_CI),
    (steps.worker(steps.Task.FIRST_ROUND), Kind.FIRST_ROUND),
    (steps.worker(steps.Task.RESOLVE_CONFLICT), Kind.RESOLVE_CONFLICT),
    (REVIEW_STEP, Kind.REVIEW),
    (steps.regular_review(steps.Stage.PLAN_ONLY), Kind.REVIEW),
    (steps.merge(), None),
    (steps.undraft(), None),
    (steps.wait_for_ci(), None),
    (steps.wait_for_undraft(), None),
    (steps.wait_for_owner(), None),
    (steps.opus_ruling(), None),
    (steps.pause_for_owner(), None),
]


class TestPullItems(unittest.TestCase):
    """The fixes and reviews open PRs need."""

    def test_categories(self) -> None:
        """A PR is listed as the kind of work its step is, or as none."""
        found = [
            [each.category for each in work.pull_items([stepped(facts(1, NONE), step)])]
            for step, _ in STEP_CASES
        ]
        expected = [[kind] if kind else [] for _, kind in STEP_CASES]
        assert_that(found, equal_to(expected))

    def test_the_category_comes_from_the_step_alone(self) -> None:
        """A PR behind the base is listed as its step says, not as an update."""
        found = [
            [
                each.category
                for each in work.pull_items(
                    [stepped(facts(1, NONE, mergeable_state="behind"), step)]
                )
            ]
            for step, _ in STEP_CASES
        ]
        expected = [[kind] if kind else [] for _, kind in STEP_CASES]
        assert_that(found, equal_to(expected))


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
    "body": "see https://github.com/owner/project/issues/2 and lib#3",
    "head": {"sha": fakes.HEAD, "ref": "claude/work-4"},
}


class TestTickets(unittest.TestCase):
    """Open tickets that no open PR names."""

    def test_taken_and_offered(self) -> None:
        """Only a ticket an open PR names is left out; named paths do not count."""
        named = facts(10, NONE, **NAMING)
        plain = facts(11, NONE, head={"sha": fakes.HEAD, "ref": "feature"})
        api = fakes.github(dict(TICKET_BODIES))
        in_progress = work.taken([named, plain])
        offered = work.ticket_items(
            api, dataclasses.replace(SETTINGS, slots=SLOTS), in_progress
        )
        found = ("owner/lib#3" in in_progress, [each.reference for each in offered])
        assert_that(found, equal_to((True, ["owner/project#5", "owner/project#6"])))


class TestOrderAndAssign(unittest.TestCase):
    """Sorting and filling empty slots."""

    def test_order(self) -> None:
        """PRs oldest first, then tickets by priority and age; held are left out."""
        newer = work.Item(
            category=work.Category.NEW_PR, reference="b", created_at="2027", title="t"
        )
        items = [
            item("c", work.Category.NEW_PR, priority=1),
            newer,
            item("a", work.Category.NEW_PR),
            item("x", work.Category.REVIEW),
            item("held", work.Category.FIX_REVIEW),
        ]
        found = work.ordered(items, ["held"])
        assert_that([each.reference for each in found], equal_to(["x", "a", "b", "c"]))

    def test_order_across_kinds(self) -> None:
        """A review comes before a fix and a fix before a ticket, whatever the age."""
        items = [
            dataclasses.replace(item(name, category), created_at=created)
            for name, category, created in [
                ("ticket", work.Category.NEW_PR, "2020"),
                ("fix", work.Category.FIX_REVIEW, "2026-03"),
                ("review", work.Category.REVIEW, "2026-01"),
            ]
        ]
        found = work.ordered(items, [])
        assert_that(
            [each.reference for each in found],
            equal_to(["review", "fix", "ticket"]),
        )

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

    def test_assign(self) -> None:
        """The smallest empty slot takes the first item it may take."""
        book = ledger.Ledger(
            slots=(
                ledger.Slot(name="big", model="large"),
                ledger.Slot(name="tiny", model="small"),
                ledger.Slot(name="busy", model="small", agent="a", task="t"),
                ledger.Slot(name="odd", model="unknown"),
            ),
            failed={},
        )
        items = [
            item("first", work.Category.NEW_PR),
            item("hard", work.Category.NEW_PR, labels=["hard"]),
        ]
        found = work.assign(items, book, SLOTS)
        assert_that(
            [(slot.name, chosen and chosen.reference) for slot, chosen in found],
            equal_to([("tiny", "first"), ("big", "hard"), ("odd", None)]),
        )
