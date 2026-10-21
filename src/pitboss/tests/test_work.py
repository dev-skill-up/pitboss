"""Tests for what to start next."""

import dataclasses
import json
import pathlib
import tempfile
import unittest

from hamcrest import assert_that, contains_exactly, equal_to, is_, none

from .. import config, ledger, pulls, reviews, shapes, work
from . import fakes

REPO = config.Repo(owner="owner", name="project")
GREEN = shapes.CheckRun(id=1, name="build", finished=True, failed=False)
SLOTS = config.Slots(
    ledger=pathlib.Path("/unused"),
    default=(),
    models=("small", "large"),
    priority_labels=("urgent", "later"),
    model_labels={"hard": "large", "odd": "unknown"},
)


def _facts(number: int, standing: reviews.Standing, **changes: object) -> pulls.PullFacts:
    pull = shapes.pull(_json(fakes.pull_body(number, **changes)))
    return pulls.PullFacts(
        repo=REPO, pull=pull, checks=(GREEN,), review=None, standing=standing
    )


def _json(value: object) -> str:
    return json.dumps(value)


class TestPullItems(unittest.TestCase):
    """The fixes and reviews open PRs need."""

    def test_categories(self) -> None:
        """Changes-needed is a fix; green with no review of the head is a review."""
        facts = [
            _facts(1, reviews.Standing.CHANGES_NEEDED),
            _facts(2, reviews.Standing.NONE),
            _facts(3, reviews.Standing.OLDER_HEAD),
            _facts(4, reviews.Standing.APPROVED),
            _facts(5, reviews.Standing.NONE, draft=True),
            _facts(6, reviews.Standing.NONE, mergeable_state="dirty"),
        ]
        found = work.pull_items(facts)
        assert_that(
            [(item.reference, item.category) for item in found],
            contains_exactly(
                ("owner/project#1", work.Category.FIX_REVIEW),
                ("owner/project#2", work.Category.REVIEW),
                ("owner/project#3", work.Category.REVIEW),
            ),
        )


class TestTickets(unittest.TestCase):
    """Open tickets that no open PR covers."""

    def test_taken_and_offered(self) -> None:
        """A ticket an open PR names or touches is left out."""
        facts = [
            _facts(
                10,
                reviews.Standing.NONE,
                title="Fixes #1",
                body="see https://github.com/owner/project/issues/2 and lib#3",
                head={"sha": fakes.SHA_A, "ref": "claude/work-4"},
            ),
            _facts(11, reviews.Standing.NONE, head={"sha": fakes.SHA_A, "ref": "feature"}),
        ]
        issues = [
            {"number": number, "title": f"T{number}", "created_at": f"2026-10-0{number}",
             "labels": [{"name": "urgent"}], "body": body}
            for number, body in [
                (1, ""), (2, ""), (4, ""), (5, "Change `src/thing/` please"),
                (6, "Change `docs/other.md`"),
            ]
        ]
        api = fakes.github(
            {
                fakes.page("repos/owner/project/pulls/10/files"): [
                    {"filename": "src/thing/a.py"}
                ],
                fakes.page("repos/owner/project/pulls/11/files"): [],
                fakes.page("repos/owner/project/issues?state=open&labels=urgent"): issues,
                fakes.page("repos/owner/project/issues?state=open&labels=later"): [
                    issues[4]
                ],
            }
        )
        settings = fakes.settings(pathlib.Path(tempfile.mkdtemp()))
        settings = _with_slots(settings)
        taken = work.read_taken(api, facts)
        assert_that("owner/lib#3" in taken.references, is_(True))
        found = work.ticket_items(api, settings, taken)
        assert_that(
            [(item.reference, item.priority) for item in found],
            contains_exactly(("owner/project#6", 0)),
        )


def _with_slots(settings: config.Config) -> config.Config:
    return dataclasses.replace(settings, slots=SLOTS)


def _item(reference: str, category: work.Category, **changes: object) -> work.Item:
    base = work.Item(category=category, reference=reference, created_at="2026", title="t")
    return dataclasses.replace(base, **changes)


class TestOrderAndAssign(unittest.TestCase):
    """Sorting and filling empty slots."""

    def test_order(self) -> None:
        """Category, then priority, then age; held items are left out."""
        items = [
            _item("c", work.Category.NEW_PR, priority=1),
            _item("b", work.Category.NEW_PR, priority=0, created_at="2027"),
            _item("a", work.Category.NEW_PR, priority=0),
            _item("x", work.Category.REVIEW),
            _item("held", work.Category.FIX_REVIEW),
        ]
        found = work.ordered(items, ["held"])
        assert_that([item.reference for item in found], equal_to(["x", "a", "b", "c"]))

    def test_smallest_model(self) -> None:
        """Labels raise the floor; failures move up; all failed is none."""
        hard = _item("h", work.Category.NEW_PR, labels=frozenset({"hard", "odd"}))
        plain = _item("p", work.Category.NEW_PR)
        assert_that(work.smallest_model(hard, SLOTS, {}), equal_to("large"))
        assert_that(work.smallest_model(plain, SLOTS, {"p": ["small"]}), equal_to("large"))
        assert_that(
            work.smallest_model(plain, SLOTS, {"p": ["small", "large"]}), is_(none())
        )

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
            _item("first", work.Category.NEW_PR),
            _item("hard", work.Category.NEW_PR, labels=frozenset({"hard"})),
        ]
        found = work.assign(items, book, SLOTS)
        assert_that(
            [(slot.name, item and item.reference) for slot, item in found],
            contains_exactly(("tiny", "first"), ("big", "hard"), ("odd", None)),
        )
