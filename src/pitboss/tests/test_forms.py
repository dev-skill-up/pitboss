"""Tests for the form checks and ``lint pr-body|review|brief``."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import config, forms
from .formchecks import body_checks, checks, subject
from .linting import BODY, FOOTER, HEAD, lines, lint, write_text
from .test_reviews import form as review_form

OTHER = "b" * 40
WITH_FOOTER = BODY + FOOTER + "\n"
FORM = review_form("## Review", "Reviewed: {sha}", "Verdict: {verdict}")
ONE_LINE = review_form("Independent review of head {sha}: {verdict}")
BARE = review_form("Hello", "world")
GATED = review_form("## Adversarial review", "Reviewed: {sha}", "Verdict: {verdict}")
REVIEW = f"## Adversarial review\n\nReviewed: {HEAD}\nVerdict: approved\n"
PROJECT = "[project]\nowner = 'o'\nrepository = 'r'\nmain_clone = '/c'\n"
FORMS_TOML = PROJECT + """
[review.form]
lines = ["Looked at {sha}: {verdict}"]
[review.gated_form]
lines = ["## Strict", "Head: {sha}", "Outcome: {verdict}"]
[lint.pr_body]
footers = ["-- me"]
[lint.brief]
required = ["Overlap:"]
"""
TICKET = (
    "Title\n\nDone when:\n\n## Done when\n- it works\n- it is tested\n\n## Notes\nx\n"
)


def review_checks(
    body: str, form: config.ReviewForm = FORM, head: str = HEAD
) -> Sequence[str]:
    """The checks a review fails read as a person reads it.

    Args:
        body: the review.
        form: its form.
        head: the head given.

    Returns:
        The failed checks' names.
    """
    return checks(forms.ordinary_review(subject(body, head), form))


def gated_checks(body: str, head: str = HEAD) -> Sequence[str]:
    """The checks a review fails read as the gate reads it.

    Args:
        body: the review.
        head: the head given.

    Returns:
        The failed checks' names.
    """
    return checks(forms.gated_review(subject(body, head), GATED))


class TestPrBody(unittest.TestCase):
    """The form of a PR body."""

    def test_a_good_body_is_accepted(self) -> None:
        """First line, one ticket, the head and evidence: no finding, no footer."""
        tildes = BODY.replace("```", "~~~").replace("#12", "o/r#12")
        found = [body_checks(BODY), body_checks(BODY, head=""), body_checks(tildes)]
        assert_that(found, equal_to([[], [], []]))

    def test_first_line(self) -> None:
        """A body whose first line is not Fixes, or an empty one, is refused."""
        refs = BODY.replace("Fixes #12", "Refs #12")
        found = [body_checks(refs), body_checks("")]
        every = ["first-line", "head", "evidence"]
        assert_that(found, equal_to([["first-line"], every]))

    def test_one_ticket(self) -> None:
        """Two tickets are refused; the same one twice, in any case, is not."""
        two = BODY.replace("---\n", "Fixes #13\n---\n")
        same = BODY.replace("---\n", "fixes #12\n---\n")
        assert_that(body_checks(two), equal_to(["one-ticket"]))
        assert_that(body_checks(same), equal_to([]))
        message = forms.pr_body(subject(two), ())[0]
        assert_that(message, contains_string("(#12, #13)"))

    def test_head(self) -> None:
        """A missing Head line, or one for another head, is refused; the last counts."""
        newest = BODY.replace("---\n", f"Head: {OTHER}\n---\n")
        found = [
            body_checks(BODY.replace(f"Head: {HEAD}", "")),
            body_checks(BODY, head=OTHER),
            body_checks(newest, head=OTHER),
            body_checks(newest),
        ]
        assert_that(found, equal_to([["head"], ["head"], [], ["head"]]))

    def test_evidence(self) -> None:
        """An Evidence heading and a fenced block that starts with a command."""
        no_heading = BODY.replace("## Evidence", "## Results")
        no_command = BODY.replace("$ nox -s tests", "OK")
        found = [body_checks(no_heading), body_checks(no_command)]
        assert_that(found, equal_to([["evidence"], ["evidence"]]))

    def test_footer(self) -> None:
        """No footer is required by default; a configured one must end the body."""
        far = WITH_FOOTER.replace(FOOTER, "x\ny\nz").replace(
            "Head:", f"{FOOTER}\nHead:", 1
        )
        default = config.default_lint().footers
        found = [
            checks(forms.pr_body(subject(BODY), default)),
            body_checks(BODY, footers=(FOOTER,)),
            body_checks(WITH_FOOTER, footers=(FOOTER,)),
            body_checks(BODY, footers=("thanks",)),
            body_checks(far, footers=(FOOTER,)),
        ]
        assert_that(found, equal_to([[], ["footer"], [], ["footer"], ["footer"]]))

    def test_finding_names_its_check_last(self) -> None:
        """A finding is the file, the message and the check in parentheses."""
        found = forms.pr_body(forms.Subject(name="b.md", body="x", head=""), ())
        assert_that(found[0], contains_string("b.md: the first line is"))
        assert_that(found[0].endswith("(first-line)"), equal_to(True))


class TestReview(unittest.TestCase):
    """The form of a review."""

    def test_accepted(self) -> None:
        """Each form accepts a text in its form, the head abbreviated or not."""
        short = "## Review\nReviewed: aaaaaaa\nVerdict: changes needed\n"
        one = f"Independent review of head {HEAD}: approved   \n"
        found = [
            review_checks(short),
            review_checks(one, ONE_LINE),
            gated_checks(REVIEW),
            gated_checks(REVIEW, head=""),
        ]
        assert_that(found, equal_to([[], [], [], []]))

    def test_first_line(self) -> None:
        """The first line must be the form's first line; an empty text is refused."""
        wrong = REVIEW.replace("## Adversarial review", "## Review")
        later = f"intro\nIndependent review of head {HEAD}: approved\n"
        found = [
            gated_checks(wrong),
            review_checks("", ONE_LINE),
            review_checks(later, ONE_LINE),
        ]
        assert_that(found, equal_to([["first-line"]] * 3))

    def test_the_other_lines(self) -> None:
        """A missing Reviewed or Verdict line, or another verdict word, is refused."""
        no_reviewed = REVIEW.replace(f"Reviewed: {HEAD}\n", "")
        no_verdict = REVIEW.replace("Verdict: approved\n", "")
        maybe = REVIEW.replace("approved", "maybe")
        found = [
            checks(forms.ordinary_review(subject(each), GATED))
            for each in (no_reviewed, no_verdict, maybe)
        ]
        assert_that(found, equal_to([["reviewed"], ["verdict"], ["verdict"]]))
        assert_that(review_checks("Hello\n", BARE), equal_to(["form"]))

    def test_gated_wants_each_line_once(self) -> None:
        """A strict form refuses a line twice, a word elsewhere, trailing space."""
        twice = REVIEW + "Verdict: approved\n"
        word = REVIEW + "I wrote Verdict: elsewhere\n"
        spaced = REVIEW.replace("approved", "approved ")
        found = [gated_checks(twice), gated_checks(word), gated_checks(spaced)]
        assert_that(found, equal_to([["exact"], ["exact"], ["verdict"]]))
        loose = [review_checks(twice, GATED), review_checks(spaced, GATED)]
        assert_that(loose, equal_to([[], []]))

    def test_gated_is_plain(self) -> None:
        """A strict form refuses non-ASCII, a fence, a tag and a link definition."""
        extras = ("café", "```x```", "<b>hi</b>", "[1]: http://x")
        found = [gated_checks(REVIEW + each + "\n") for each in extras]
        assert_that(found, equal_to([["plain"]] * len(extras)))
        assert_that(review_checks(REVIEW + "<b>hi</b>\n", GATED), equal_to([]))

    def test_head(self) -> None:
        """The reviewed head must be the PR's; a strict form wants all 40 digits."""
        short = REVIEW.replace(HEAD, "aaaaaaa")
        found = [
            gated_checks(REVIEW, head=OTHER),
            gated_checks(short),
            review_checks(short, GATED),
            review_checks(short, GATED, head=OTHER),
        ]
        assert_that(found, equal_to([["head"], ["head"], [], ["head"]]))


class TestBrief(unittest.TestCase):
    """The form of a brief."""

    def test_required_lines(self) -> None:
        """Each required line start must begin a line of the brief."""
        good = checks(
            forms.brief(subject("Work.\n  Overlap: none\n"), ("Overlap:",), None)
        )
        bad = checks(forms.brief(subject("Work.\n"), ("Overlap:", "Work"), None))
        assert_that((good, bad), equal_to(([], ["required-line"])))

    def test_done_when(self) -> None:
        """A ticket's Done-when lines are in the brief word for word."""
        good = "Do it.\n- it works\n- it is tested\n"
        cases = [(good, TICKET), ("- it works\n", TICKET), (good, "Title only\n")]
        found = [checks(forms.brief(subject(text), (), each)) for text, each in cases]
        assert_that(found, equal_to([[], ["done-when"], ["done-when"]]))
        missing = forms.brief(subject("x\n"), (), TICKET)
        assert_that(missing, has_length(2))
        assert_that(missing[0], contains_string("- it works"))


def outcome(kind: str, body: str, *options: str) -> tuple[object, str]:
    """Run ``pitboss lint`` on a text.

    Args:
        kind: the kind of check.
        body: the text.
        *options: the options after the file.

    Returns:
        The exit code, and the last word of the first line printed.
    """
    ran = lint(kind, write_text("text.md", body), *options)
    shown = lines(ran) or ran.err.splitlines()
    return ran.code, shown[0].split()[-1]


class TestCommands(unittest.TestCase):
    """``pitboss lint pr-body``, ``review`` and ``brief``."""

    def test_pr_body(self) -> None:
        """A good body is 0, a bad one 1 with its check named."""
        refs = BODY.replace("Fixes #12", "Refs #12")
        found = [
            outcome("pr-body", BODY, "--head", HEAD),
            outcome("pr-body", refs, "--head", HEAD),
            outcome("pr-body", BODY, "--head", OTHER),
        ]
        assert_that(found, equal_to([(0, "ok"), (1, "(first-line)"), (1, "(head)")]))

    def test_one_file(self) -> None:
        """A form check reads one file; a missing one is a usage error."""
        one = write_text("one.md", BODY)
        two = write_text("two.md", BODY)
        ran = [lint("pr-body", one, two), lint("pr-body", "/no/such.md")]
        assert_that([each.code for each in ran], equal_to([2, 2]))
        assert_that(ran[0].err, contains_string("pr-body checks one file, not 2"))

    def test_the_phrases_are_checked_too(self) -> None:
        """A banned phrase in a form-correct text is found by the phrase check."""
        mine = write_text("mine.tsv", "mine\tpurple\tpurple\tSay blue.\n")
        spoiled = BODY.replace("---\n", "purple\n")
        found = outcome("pr-body", spoiled, "--phrases", mine, "--head", HEAD)
        assert_that(found, equal_to((1, "blue.")))

    def test_review(self) -> None:
        """The generic form; with --gated the gated one (the same by default)."""
        text = f"## Review\nReviewed: {HEAD}\nVerdict: approved\n"
        found = [
            outcome("review", text, "--head", HEAD),
            outcome("review", REVIEW, "--head", HEAD),
            outcome("review", text, "--head", HEAD, "--gated"),
            outcome("review", text, "--gated", "--head", OTHER),
        ]
        expected = [(0, "ok"), (1, "(first-line)"), (0, "ok"), (1, "(head)")]
        assert_that(found, equal_to(expected))

    def test_config(self) -> None:
        """The forms are the project's: its review lines, footers and brief lines."""
        path = write_text("project.toml", FORMS_TOML)
        strict = f"## Strict\nHead: {HEAD}\nOutcome: approved\n"
        mine = f"Looked at {HEAD}: approved\n"
        found = [
            outcome("review", mine, "--config", path),
            outcome("review", strict, "--config", path, "--gated"),
            outcome("pr-body", BODY, "--config", path),
            outcome("brief", "Overlap: none\n", "--config", path),
            outcome("brief", "Work.\n", "--config", path),
        ]
        every = [
            (0, "ok"),
            (0, "ok"),
            (1, "(footer)"),
            (0, "ok"),
            (1, "(required-line)"),
        ]
        assert_that(found, equal_to(every))

    def test_bad_config(self) -> None:
        """A configuration that is missing, not TOML or without a project is 2."""
        broken = write_text("broken.toml", "[project\n")
        no_project = write_text("none.toml", "[review]\n")
        text = write_text("a.md", REVIEW)
        ran = [
            lint("review", text, "--config", each)
            for each in ("/no/such.toml", broken, no_project)
        ]
        assert_that([each.code for each in ran], equal_to([2, 2, 2]))
        assert_that(ran[0].err, contains_string("/no/such.toml"))

    def test_brief_with_a_ticket(self) -> None:
        """--ticket adds the Done-when lines; an unreadable ticket is 2."""
        ticket = write_text("ticket.md", TICKET)
        good = "- it works\n- it is tested\n"
        found = [
            outcome("brief", good, "--ticket", ticket),
            outcome("brief", "- it works\n", "--ticket", ticket),
            outcome("brief", good, "--ticket", "/no/such/ticket.md"),
            outcome("brief", good),
        ]
        expected = [(0, "ok"), (1, "(done-when)"), (2, "directory"), (0, "ok")]
        assert_that(found, equal_to(expected))
