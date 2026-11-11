"""A7 a split verdict is changes needed, A8 a review never says "makes false".

Rule ids A7 and A8 of ``rules.tsv`` (pitboss#444, items 4 and 38).
"""

import unittest

from hamcrest import assert_that, contains_string, empty, equal_to, has_length

from .. import config, reviewrules, reviews, shapes

HEAD = "a" * 40


def _read(body: str) -> reviews.Found:
    comment = shapes.Comment(
        body=body, author_association="MEMBER", created_at="2026-11-11T00:00:00Z"
    )
    trusted = frozenset({"MEMBER"})
    form = config.DEFAULT_REVIEW_FORM
    (found,) = reviews.from_comments([comment], trusted, reviews.read_comment, form)
    return found


def _review(plan: str, execution: str, verdict: str) -> str:
    return (
        f"## Review\nReviewed: {HEAD}\nPlan: {plan}\nExecution: {execution}\n"
        f"Verdict: {verdict}\n"
    )


class TestSplitVerdict(unittest.TestCase):
    """A review gives one verdict for the whole PR."""

    def test_a7_either_split_is_changes_needed(self) -> None:
        """Pitboss 465: Plan approved beside Execution changes needed, and back."""
        for plan, execution, verdict in (
            ("approved", "changes needed", "changes needed"),
            ("changes needed", "approved", "approved"),
        ):
            with self.subTest(plan=plan):
                found = _read(_review(plan, execution, verdict))
                assert_that(found.verdict, equal_to(shapes.Verdict.CHANGES_NEEDED))
                assert_that(
                    reviewrules.is_split(_review(plan, execution, verdict)),
                    equal_to(True),
                )

    def test_a7_whole_approval_stays_approved(self) -> None:
        """Both lines approving is an approval, and is not split."""
        found = _read(_review("approved", "approved", "approved"))
        assert_that(found.verdict, equal_to(shapes.Verdict.APPROVED))
        assert_that(
            reviewrules.is_split(_review("approved", "approved", "approved")),
            equal_to(False),
        )


class TestMadeFalse(unittest.TestCase):
    """The words that say a change makes text false are refused."""

    def test_a8_makes_false_is_refused_with_its_line(self) -> None:
        """Pitboss 465 finding 1 and 470 finding 3."""
        found = reviewrules.phrase_findings("ok\nthe docstring the change made false\n")
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("line 2"))
        assert_that(found[0], contains_string("say what the text now says instead"))

    def test_a8_makes_the_comment_false_is_refused(self) -> None:
        """A few words between the verb and the word are the same phrase."""
        found = reviewrules.phrase_findings("It makes the Comment false.")
        assert_that(found, has_length(1))

    def test_a8_a_review_without_the_phrase_passes(self) -> None:
        """The nearest input that must still pass."""
        assert_that(reviewrules.phrase_findings("The docstring says X."), empty())
