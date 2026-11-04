"""Tests for a PR that closes several tickets (keyword: fold, pitboss#171)."""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import foldline, folds, forms, headchecks, pulls, shapes
from . import test_stall
from .formchecks import body_checks, subject
from .linting import BODY, lines, lint, write_text

URL = "https://github.com/o/r/pull/7#issuecomment-1"
OTHER_URL = "https://github.com/o/r/pull/7#issuecomment-2"
STEPS = "Opus ruling\nRuling: do these steps\n"
SPLIT = "Opus ruling\nRuling: split\n"
TWO = BODY.replace("Fixes #12", "Fixes #12\nCloses #13")
CITED = TWO.replace("Head:", f"Ruling: {URL}\n\nHead:")


def facts(body: str, rulings: Sequence[folds.Recorded]) -> pulls.PullFacts:
    """A PR with a body and its ruling comments.

    Args:
        body: its body.
        rulings: the address and text of each ruling comment.

    Returns:
        The PR.
    """
    base = test_stall.facts("fold", [])
    pull = dataclasses.replace(base.pull, body=body)
    signals = headchecks.HeadSignals(rulings=rulings)
    return dataclasses.replace(base, pull=pull, signals=signals)


class TestFolds(unittest.TestCase):
    """The tickets a body closes and the ruling that allows several."""

    def test_tickets(self) -> None:
        """Fixes and Closes count, once each, in any case."""
        found = folds.tickets("Fixes #1\nCLOSES o/r#2\ncloses #1\nRefs #3\n")
        assert_that(found, equal_to(["#1", "O/R#2"]))

    def test_recorded(self) -> None:
        """Only a trusted author's ruling comment is recorded."""
        comments = [
            shapes.Comment(
                body=body, author_association=who, created_at="", url=f"u{who}"
            )
            for body, who in [(STEPS, "OWNER"), (STEPS, "NONE"), ("hello", "OWNER")]
        ]
        found = folds.ruling_comments(comments, {"OWNER"})
        assert_that(found, equal_to([("uOWNER", STEPS)]))

    def test_allows(self) -> None:
        """Only a cited ruling comment that rules do these steps allows it."""
        found = [
            folds.allows(CITED, [(URL, STEPS)]),
            folds.allows(CITED, [(URL, SPLIT)]),
            folds.allows(CITED, [(OTHER_URL, STEPS)]),
            folds.allows(CITED, [(URL, "Ruling: do these steps\n")]),
            folds.allows(CITED, [("", STEPS)]),
            folds.allows(CITED, []),
        ]
        assert_that(found, equal_to([True, False, False, False, False, False]))


class TestLintBody(unittest.TestCase):
    """``lint pr-body`` and several tickets."""

    def test_closes_counts(self) -> None:
        """Fixes and Closes for two tickets are refused; one ticket is not."""
        one = BODY.replace("Fixes #12", "Fixes #12\nCloses #12")
        found = [body_checks(TWO), body_checks(one)]
        assert_that(found, equal_to([["one-ticket"], []]))

    def test_message(self) -> None:
        """The finding names the tickets and the ruling that would allow them."""
        message = forms.pr_body(subject(TWO), ())[0]
        assert_that(message, contains_string("(#12, #13)"))
        assert_that(message, contains_string("Ruling: do these steps"))

    def test_ruling_allows(self) -> None:
        """A cited ruling comment of do these steps allows it; split does not."""
        allowed = forms.pr_body(subject(CITED), (), [(URL, STEPS)])
        split = forms.pr_body(subject(CITED), (), [(URL, SPLIT)])
        uncited = forms.pr_body(subject(TWO), (), [(URL, STEPS)])
        assert_that(allowed, equal_to([]))
        assert_that(split, has_length(1))
        assert_that(uncited, has_length(1))

    def test_command(self) -> None:
        """The command takes the ruling's address and its file."""
        body = write_text("body.md", CITED)
        ruling = write_text("ruling.md", STEPS)
        split = write_text("split.md", SPLIT)
        given = [
            lint("pr-body", body, "--ruling", URL, ruling),
            lint("pr-body", body, "--ruling", URL, split),
            lint("pr-body", body),
        ]
        codes = [each.code for each in given]
        assert_that(codes, equal_to([0, 1, 1]))
        assert_that(lines(given[0]), equal_to(["ok"]))


class TestFoldedLine(unittest.TestCase):
    """The sweep's FOLDED PR line."""

    def test_line(self) -> None:
        """An open PR whose body folds tickets with no ruling gets a line."""
        found = foldline.lines(facts(TWO, []))
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("FOLDED PR o/r#7:"))
        assert_that(found[0], contains_string("2 tickets (#12, #13)"))

    def test_no_line(self) -> None:
        """One ticket, or a cited allowing ruling, gets none."""
        found = [
            foldline.lines(facts(BODY, [])),
            foldline.lines(facts(CITED, [(URL, STEPS)])),
        ]
        assert_that(found, equal_to([[], []]))
