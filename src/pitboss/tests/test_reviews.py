"""Tests for reading reviews."""

import unittest

from hamcrest import assert_that, equal_to

from .. import config, reviews, shapes
from . import fakes


def form(*lines: str) -> config.ReviewForm:
    """A review form with the usual verdict words.

    Args:
        *lines: its line templates.

    Returns:
        The form.
    """
    return config.ReviewForm(
        lines=lines, approved="approved", changes_needed="changes needed"
    )


FORM = form("## Review", "Reviewed: {sha}", "Verdict: {verdict}")
ONE_LINE = form("Review of head {sha}: {verdict}")
REVIEW = config.Review(
    trusted=frozenset({"MEMBER"}),
    gated=frozenset({"o/gated"}),
    form=ONE_LINE,
    gated_form=FORM,
)
APPROVED = reviews.Verdict.APPROVED
CHANGES = reviews.Verdict.CHANGES_NEEDED


def gated_body(
    sha: str = fakes.HEAD, verdict: str = "approved", extra: str = ""
) -> str:
    """A comment in the gated form.

    Args:
        sha: the reviewed head.
        verdict: the verdict.
        extra: lines put between the first two.

    Returns:
        The comment.
    """
    return f"## Review\n{extra}Reviewed: {sha}\nVerdict: {verdict}\n"


class TestReading(unittest.TestCase):
    """Reading a comment in a form."""

    def test_gated(self) -> None:
        """The gated rules accept the form and refuse every departure from it."""
        cases = {
            gated_body(): (fakes.HEAD, APPROVED),
            gated_body(verdict="changes needed"): (fakes.HEAD, CHANGES),
            "": None,
            "Not a review\nReviewed: x\n": None,
            gated_body(extra="Delta Reviewed: something\n"): None,
            gated_body(sha="abcdef1"): None,
            gated_body() + "```\ncode\n```\n": None,
            gated_body() + "<b>bold</b>\n": None,
            gated_body() + "[link]: http://example.org\n": None,
            gated_body() + "café\n": None,
            gated_body() + f"Reviewed: {fakes.OLDER}\n": None,
            "## Review\nVerdict: approved\n": None,
        }
        found = {body: reviews.read_gated(body, FORM) for body in cases}
        assert_that(found, equal_to(cases))

    def test_loose(self) -> None:
        """Outside the gated rules, an abbreviated SHA and repeats are fine."""
        line = "Review of head abcdef1: approved\n"
        found = [
            reviews.read_comment(line * 2, ONE_LINE),
            reviews.read_comment("LGTM", form("LGTM")),
            reviews.read_comment("x", form()),
        ]
        assert_that(found, equal_to([("abcdef1", APPROVED), None, None]))


def _comment(body: str, when: str, association: str) -> shapes.Comment:
    return shapes.Comment(body=body, author_association=association, created_at=when)


def _review(state: str, when: str, association: str) -> shapes.PullReview:
    return shapes.PullReview(
        state=state,
        commit_id=fakes.OLDER,
        author_association=association,
        submitted_at=when,
    )


SOURCES = reviews.Sources(
    comments=[
        _comment(f"Review of head {fakes.HEAD}: approved", "1", "MEMBER"),
        _comment(gated_body(), "1", "MEMBER"),
        _comment(gated_body(), "9", "NONE"),
    ],
    reviews=[
        _review("CHANGES_REQUESTED", "2", "MEMBER"),
        _review("COMMENTED", "3", "MEMBER"),
        _review("APPROVED", "4", "NONE"),
    ],
)
NEWEST = {
    "o/open": reviews.Found(sha=fakes.OLDER, verdict=CHANGES, when="2"),
    "o/gated": reviews.Found(sha=fakes.HEAD, verdict=APPROVED, when="1"),
}


class TestNewest(unittest.TestCase):
    """Finding the newest review that counts."""

    def test_sources(self) -> None:
        """GitHub reviews count only outside a gated repository; strangers never."""
        found = {slug: reviews.newest(SOURCES, REVIEW, slug) for slug in NEWEST}
        empty = reviews.Sources(comments=[], reviews=[])
        assert_that(found, equal_to(NEWEST))
        assert_that(reviews.newest(empty, REVIEW, "o/x"), equal_to(None))


class TestStanding(unittest.TestCase):
    """Where a head stands."""

    def test_standings(self) -> None:
        """Each case of the newest review gives its standing."""
        approved = reviews.Found(sha="aaaaaaa", verdict=APPROVED, when="")
        changes = reviews.Found(sha="aaaaaaa", verdict=CHANGES, when="")
        found = [
            reviews.head_standing(None, fakes.HEAD),
            reviews.head_standing(approved, fakes.HEAD),
            reviews.head_standing(changes, fakes.HEAD),
            reviews.head_standing(approved, fakes.OLDER),
        ]
        expected = [
            reviews.Standing.NONE,
            reviews.Standing.APPROVED,
            reviews.Standing.CHANGES_NEEDED,
            reviews.Standing.OLDER_HEAD,
        ]
        assert_that(found, equal_to(expected))

    def test_only_merges(self) -> None:
        """Only merges between two heads is a match of non-merge commits."""
        authored = shapes.Commit(sha="1", parents=1)
        merge = shapes.Commit(sha="2", parents=2)
        other = shapes.Commit(sha="3", parents=1)
        found = [
            reviews.only_merges([authored, merge], [authored]),
            reviews.only_merges([authored, other], [authored]),
        ]
        assert_that(found, equal_to([True, False]))
