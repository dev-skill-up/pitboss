"""Tests for reading reviews."""

import unittest

from hamcrest import assert_that, equal_to, is_, none

from .. import config, reviews, shapes
from . import fakes

FORM = config.ReviewForm(
    lines=("## Review", "Reviewed: {sha}", "Verdict: {verdict}"),
    approved="approved",
    changes_needed="changes needed",
)
ONE_LINE = config.ReviewForm(
    lines=("Review of head {sha}: {verdict}",),
    approved="approved",
    changes_needed="changes needed",
)
REVIEW = config.Review(
    trusted=frozenset({"MEMBER"}),
    gated=frozenset({"o/gated"}),
    form=ONE_LINE,
    gated_form=FORM,
)


def _gated(sha: str = fakes.SHA_A, verdict: str = "approved", extra: str = "") -> str:
    return f"## Review\n{extra}Reviewed: {sha}\nVerdict: {verdict}\n"


class TestReadComment(unittest.TestCase):
    """Reading a comment in a form."""

    def test_strict_approval(self) -> None:
        """A comment in the gated form is read."""
        found = reviews.read_gated(_gated(), FORM)
        assert_that(found, equal_to((fakes.SHA_A, reviews.Verdict.APPROVED)))

    def test_changes(self) -> None:
        """The other verdict asks for changes."""
        found = reviews.read_gated(_gated(verdict="changes needed"), FORM)
        assert_that(found, equal_to((fakes.SHA_A, reviews.Verdict.CHANGES_NEEDED)))

    def test_strict_refusals(self) -> None:
        """The gated rules each refuse a comment."""
        for body in [
            "",
            "Not a review\nReviewed: x\n",
            _gated(extra="Delta Reviewed: something\n"),
            _gated(sha="abcdef1"),
            _gated() + "```\ncode\n```\n",
            _gated() + "<b>bold</b>\n",
            _gated() + "[link]: http://example.org\n",
            _gated() + "café\n",
            _gated() + f"Reviewed: {fakes.SHA_B}\n",
            "## Review\nVerdict: approved\n",
        ]:
            assert_that(reviews.read_gated(body, FORM), is_(none()), body)

    def test_loose(self) -> None:
        """Outside the gated rules, an abbreviated SHA and repeats are fine."""
        body = "Review of head abcdef1: approved\nReview of head abcdef1: approved\n"
        found = reviews.read_comment(body, ONE_LINE)
        assert_that(found, equal_to(("abcdef1", reviews.Verdict.APPROVED)))

    def test_no_sha_in_form(self) -> None:
        """A form with no SHA cannot be read as a review."""
        form = config.ReviewForm(lines=("LGTM",), approved="a", changes_needed="c")
        assert_that(reviews.read_comment("LGTM", form), is_(none()))

    def test_empty_form(self) -> None:
        """A form with no lines reads nothing."""
        form = config.ReviewForm(lines=(), approved="a", changes_needed="c")
        assert_that(reviews.read_comment("x", form), is_(none()))


def _comment(body: str, when: str, association: str = "MEMBER") -> shapes.Comment:
    return shapes.Comment(body=body, author_association=association, created_at=when)


def _review(state: str, when: str, association: str = "MEMBER") -> shapes.PullReview:
    return shapes.PullReview(
        state=state,
        commit_id=fakes.SHA_B,
        author_association=association,
        submitted_at=when,
    )


class TestNewest(unittest.TestCase):
    """Finding the newest review that counts."""

    def test_github_reviews_count_when_not_gated(self) -> None:
        """A trusted GitHub review newer than a comment wins."""
        sources = reviews.Sources(
            comments=[_comment(f"Review of head {fakes.SHA_A}: approved", "1")],
            reviews=[
                _review("CHANGES_REQUESTED", "2"),
                _review("COMMENTED", "3"),
                _review("APPROVED", "4", "NONE"),
            ],
        )
        found = reviews.newest(sources, REVIEW, "o/open")
        assert_that(
            found,
            equal_to(
                reviews.Found(
                    sha=fakes.SHA_B, verdict=reviews.Verdict.CHANGES_NEEDED, when="2"
                )
            ),
        )

    def test_gated_reads_only_comments(self) -> None:
        """In a gated repository GitHub reviews do not count, nor strangers."""
        sources = reviews.Sources(
            comments=[_comment(_gated(), "1"), _comment(_gated(), "5", "NONE")],
            reviews=[_review("APPROVED", "4")],
        )
        found = reviews.newest(sources, REVIEW, "o/gated")
        assert_that(found and found.when, equal_to("1"))

    def test_none(self) -> None:
        """No review counts."""
        sources = reviews.Sources(comments=[_comment("hello", "1")], reviews=[])
        assert_that(reviews.newest(sources, REVIEW, "o/open"), is_(none()))


class TestStanding(unittest.TestCase):
    """Where a head stands."""

    def test_standings(self) -> None:
        """Each case of the newest review gives its standing."""
        approved = reviews.Found(sha="aaaaaaa", verdict=reviews.Verdict.APPROVED, when="")
        changes = reviews.Found(
            sha="aaaaaaa", verdict=reviews.Verdict.CHANGES_NEEDED, when=""
        )
        cases = [
            (None, fakes.SHA_A, reviews.Standing.NONE),
            (approved, fakes.SHA_A, reviews.Standing.APPROVED),
            (changes, fakes.SHA_A, reviews.Standing.CHANGES_NEEDED),
            (approved, fakes.SHA_B, reviews.Standing.OLDER_HEAD),
        ]
        for found, head, expected in cases:
            assert_that(reviews.head_standing(found, head), equal_to(expected))

    def test_only_merges(self) -> None:
        """Only merges between two heads is a match of non-merge commits."""
        authored = shapes.Commit(sha="1", parents=1)
        merge = shapes.Commit(sha="2", parents=2)
        other = shapes.Commit(sha="3", parents=1)
        assert_that(reviews.only_merges([authored, merge], [authored]), is_(True))
        assert_that(reviews.only_merges([authored, other], [authored]), is_(False))
