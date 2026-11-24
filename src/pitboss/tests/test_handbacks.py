"""A hand-back is what the PR shows, never a record (keyword: standing, #524)."""

import dataclasses
import unittest

from hamcrest import assert_that, equal_to

from .. import handbackderive, handbacks, shapes
from . import test_flow
from .test_plan_check_step import check_comment
from .derivedhand import held

HEAD = "a" * 40
OTHER = "b" * 40
BODY = f"## Plan\nthe plan\n\n$ echo hi\n\n## Execution\nx\n\nHead: {HEAD}\n"
NO_PLAN = "text\nHead: none\n"


def pull(body: str) -> shapes.Pull:
    """A PR with a body.

    Args:
        body: the body.

    Returns:
        The PR.
    """
    return test_flow.pull_of(body=body)


class TestDerive(unittest.TestCase):
    """The hand-back is read from the body and the comments."""

    def test_the_head_is_named_under_a_clean_check_only(self) -> None:
        """No check, a check of another Plan, or the clean check of this one."""
        trusted = frozenset({"MEMBER"})
        none = handbackderive.derive(pull(BODY), [], trusted)
        other = handbackderive.derive(
            pull(BODY),
            [check_comment("## Plan\nanother\n\n$ echo no\n")],
            trusted,
        )
        clean = handbackderive.derive(pull(BODY), [check_comment(BODY)], trusted)
        assert_that(
            [none.head, other.head, clean.head, clean.checked],
            equal_to(["", "", HEAD, ["2026-10-30T00:00:01Z"]]),
        )

    def test_a_check_of_an_untrusted_author_counts_for_nothing(self) -> None:
        """The association decides."""
        stranger = dataclasses.replace(check_comment(BODY), author_association="NONE")
        found = handbackderive.derive(pull(BODY), [stranger], frozenset({"MEMBER"}))
        assert_that((found.head, found.checked), equal_to(("", [])))

    def test_a_body_without_a_head_line_names_none(self) -> None:
        """Nothing is named, so nothing is handed back."""
        found = handbackderive.derive(pull(NO_PLAN), [], frozenset())
        assert_that(found.head, equal_to(""))


class TestCovers(unittest.TestCase):
    """What a derived hand-back covers."""

    def test_a_relock_pr_is_covered(self) -> None:
        """A relock PR owes none."""
        covered = handbacks.covers(handbacks.NOT_REQUIRED, OTHER)
        same_state = handbacks.covers_state(handbacks.NOT_REQUIRED, OTHER, "x")
        assert_that((covered, same_state), equal_to((True, True)))

    def test_the_head_must_be_the_one_the_body_names(self) -> None:
        """Another head, and no head, are not handed back."""
        found = [handbacks.covers(held(HEAD), each) for each in (HEAD, OTHER, "")]
        assert_that(found, equal_to([True, False, False]))

    def test_a_review_needs_a_clean_check_before_it(self) -> None:
        """A check posted after the review, none, and an unnamed head are no cover."""
        record = held(HEAD, "2")
        asked = [("a", "3"), ("a", "1"), ("", "3")]
        found = [handbacks.covers_state(record, *each) for each in asked]
        assert_that(found, equal_to([True, False, False]))
