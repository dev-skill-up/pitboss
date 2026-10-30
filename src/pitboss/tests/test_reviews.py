"""Tests for reading reviews."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import config, report, reviews, shapes, unreadableform
from . import fakes, test_report


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


ONE = "Independent review of head {sha}: {verdict}"
ONE_FORM = form("Independent review of head {sha}: {verdict}")
TWO = config.Review(
    trusted=frozenset({"MEMBER"}), gated=frozenset(), form=ONE_FORM, gated_form=ONE_FORM
)


def _body(verdict: str, kind: str = "review") -> str:
    return f"Independent {kind} of head {fakes.HEAD}: {verdict}\n\nfindings\n"


def _two(first: str, second: str, kind: str = "review") -> reviews.Sources:
    return reviews.Sources(
        comments=[
            _comment(_body(first), "04:04", "MEMBER"),
            _comment("x" * 70000, "04:25", "MEMBER"),
            _comment(_body(second, kind), "04:27", "MEMBER"),
        ],
        reviews=[],
    )


def _standing(sources: reviews.Sources) -> reviews.Standing:
    return reviews.head_standing(reviews.newest(sources, TWO, "o/x"), fakes.HEAD)


def _unread(sources: reviews.Sources, review: config.Review = TWO) -> str:
    slug = "o/g" if review is not TWO else "o/x"
    found = reviews.newest(sources, review, slug)
    read, rule = reviews.rules(review, slug)
    since = found.when if found else ""
    return unreadableform.unread(sources.comments, review.trusted, read, rule, since)


def _line(sources: reviews.Sources) -> str:
    found = reviews.newest(sources, TWO, "o/x")
    return report.pull_line(test_report.facts(_standing(sources), found), {})


class TestTwoReviewLines(unittest.TestCase):
    """The sweep's line for two review comments on one head."""

    def test_newer_review_decides_the_line(self) -> None:
        """Changes needed then approved says approved-this-head; the reverse not."""
        lines = [
            _line(_two("changes needed", "approved")),
            _line(_two("approved", "changes needed")),
        ]
        assert_that(lines[0], contains_string("review=approved-this-head"))
        assert_that(lines[1], contains_string("review=changes-needed"))


class TestUnread(unittest.TestCase):
    """A newer comment that tries to be a review but is not in the form."""

    def test_misspelt_form(self) -> None:
        """A re-review in another form is ignored, and said to be."""
        sources = _two("changes needed", "approved", kind="re-review")
        assert_that(_standing(sources), equal_to(reviews.Standing.CHANGES_NEEDED))
        assert_that(_unread(sources), equal_to("04:27"))

    def test_read_comments_are_not_unread(self) -> None:
        """A comment read as a review, or no attempt, or a stranger's, is not."""
        assert_that(_unread(_two("changes needed", "approved")), equal_to(""))
        strangers = reviews.Sources(
            comments=[
                _comment(_body("approved", "re-review"), "1", "NONE"),
                _comment("", "2", "MEMBER"),
                _comment("Looks fine, approved", "3", "MEMBER"),
            ],
            reviews=[],
        )
        assert_that(_unread(strangers), equal_to(""))

    def test_gated_uses_the_gated_form(self) -> None:
        """In a gated repository the gated form decides what is unread."""
        gated = config.Review(
            trusted=frozenset({"MEMBER"}),
            gated=frozenset({"o/g"}),
            form=ONE_FORM,
            gated_form=form("## Adversarial review"),
        )
        sources = _two("approved", "approved", kind="re-review")
        assert_that(_unread(sources, gated), equal_to("04:27"))


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
