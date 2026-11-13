"""Tests for a PR that closes several tickets (keyword: fold, pitboss#171)."""

import dataclasses
import json
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import (
    config,
    fixes,
    foldline,
    folds,
    forms,
    headchecks,
    parsing,
    pulls,
    reviews,
    shapes,
    steps,
)
from . import fakes
from .formchecks import body_checks, subject
from .linting import BODY, lines, lint, write_text
from .test_textlint import event, posted, run
from .says import exits

HEAD_SEVEN = {"sha": fakes.HEAD, "ref": "branch-7"}
URL = "https://github.com/o/r/pull/7#issuecomment-1"
OTHER_URL = "https://github.com/o/r/pull/7#issuecomment-2"
STEPS = "Opus ruling\nRuling: do these steps\n"
SPLIT = "Opus ruling\nRuling: split\n"
TWO = BODY.replace("Fixes #12", "Fixes #12\nCloses #13")
CITED = TWO.replace("Head:", f"Ruling: {URL}\n\nHead:")


def comment(text: str, url: str = URL, who: str = "MEMBER") -> Mapping[str, str]:
    """A comment as the API lists it.

    Args:
        text: its body.
        url: its address.
        who: its author's association.

    Returns:
        The comment's JSON object.
    """
    return {
        "body": text,
        "author_association": who,
        "created_at": "2026-11-04T00:00:00Z",
        "html_url": url,
    }


def listed(text: str, who: str = "MEMBER") -> str:
    """Write the API's list of one comment in a file.

    Args:
        text: the comment's text.
        who: its author's association.

    Returns:
        The file's path.
    """
    return write_text("comments.json", json.dumps([comment(text, URL, who)]))


def facts(body: str, rulings: Sequence[folds.Recorded]) -> pulls.PullFacts:
    """A PR with a body and its ruling comments.

    Args:
        body: its body.
        rulings: the address and text of each ruling comment.

    Returns:
        The PR.
    """
    base = pulls.PullFacts(
        repo=config.Repo(owner="o", name="r", slug="o/r"),
        pull=parsing.pull(
            json.dumps(fakes.pull_body(7, head={"sha": fakes.HEAD, "ref": "branch-7"}))
        ),
        relock=False,
        checks=[],
        review=None,
        standing=reviews.Standing.NONE,
        step=steps.ci_pending(),
    )
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

    def test_whole_address(self) -> None:
        """An address is cited whole: a longer one does not cite a shorter."""
        longer = CITED.replace(URL, URL + "2")
        found = [folds.cites(CITED, URL), folds.cites(longer, URL)]
        assert_that(found, equal_to([True, False]))
        assert_that(folds.allows(longer, [(URL, STEPS)]), equal_to(False))

    def test_read_comments(self) -> None:
        """Pages are read one after another or slurped; only trusted rulings count."""
        page = [
            comment(STEPS),
            comment("hello", OTHER_URL),
            comment(STEPS, "u", "NONE"),
        ]
        more = [comment(SPLIT, OTHER_URL)]
        listed = json.dumps(page) + "\n" + json.dumps(more) + "\n"
        slurped = json.dumps([page, more])
        trusted = {"MEMBER"}
        want = [(URL, STEPS), (OTHER_URL, SPLIT)]
        assert_that(folds.read_comments(listed, trusted), equal_to(want))
        assert_that(folds.read_comments(slurped, trusted), equal_to(want))
        assert_that(folds.read_comments("", trusted), equal_to([]))

    def test_unreadable_comments(self) -> None:
        """Text that is not a list of comments is a ValueError."""
        for text in ["not json", "[1]", '[{"body": "x"}]']:
            with self.assertRaises(ValueError):
                folds.read_comments(text, {"MEMBER"})


class TestTickets(unittest.TestCase):
    """The tickets a PR fixes are the ones it closes too."""

    def test_closes_is_fixed(self) -> None:
        """A Closes line is a ticket the PR fixes, as a Fixes line is."""
        found = fixes.fixed_tickets(facts(TWO, []))
        assert_that(found, equal_to({"o/r#12", "o/r#13"}))


class TestLintBody(unittest.TestCase):
    """``lint pr-body`` and several tickets."""

    def test_closes_counts(self) -> None:
        """Fixes and Closes for two tickets are refused; one ticket is not."""
        one = BODY.replace("Fixes #12", "Fixes #12\nCloses #12")
        found = [body_checks(TWO), body_checks(one)]
        assert_that(found, equal_to([["one-ticket"], []]))

    def test_message(self) -> None:
        """The finding names the tickets and the ruling that would allow them."""
        message = forms.pr_body(subject(TWO))[0]
        assert_that(message, contains_string("(#12, #13)"))
        assert_that(message, contains_string("Ruling: do these steps"))

    def test_ruling_allows(self) -> None:
        """A cited ruling comment of do these steps allows it; split does not."""
        allowed = forms.pr_body(subject(CITED), [(URL, STEPS)])
        split = forms.pr_body(subject(CITED), [(URL, SPLIT)])
        uncited = forms.pr_body(subject(TWO), [(URL, STEPS)])
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

    def test_comments(self) -> None:
        """The PR's comments as the API gives them hold the rulings."""
        body = write_text("body.md", CITED)
        broken = write_text("broken.json", "not json")
        files = [listed(STEPS), listed(SPLIT), listed(STEPS, "NONE")]
        files += ["/no/such/comments.json", broken]
        given = [lint("pr-body", body, "--comments", each) for each in files]
        assert_that([each.code for each in given], equal_to([0, 1, 1, 1, 2]))
        assert_that(given[4].err, contains_string("broken.json"))

    def test_comments_with_ruling(self) -> None:
        """A ruling given by hand and the comments are both read."""
        body = write_text("body.md", CITED)
        ruling = write_text("r.md", STEPS)
        given = lint(
            "pr-body", body, "--comments", listed(SPLIT), "--ruling", URL, ruling
        )
        exits(given, 0)


class TestEvent(unittest.TestCase):
    """``lint event``, which posts the ``text-lint`` status, reads the rulings."""

    def test_status_follows_the_ruling(self) -> None:
        """A cited ruling of do these steps makes the status success."""
        cited = event(CITED)
        asked = [
            (cited, ("--comments", listed(STEPS))),
            (cited, ("--comments", listed(SPLIT))),
            (cited, ("--comments", "/no/such/comments.json")),
            (cited, ()),
            (event(TWO), ("--comments", listed(STEPS))),
        ]
        found = [posted(text, *options)[1] for text, options in asked]
        states = [each["state"] for each in found]
        assert_that(states, equal_to(["success"] + ["failure"] * 4))
        assert_that(found[4]["description"], contains_string("name 2 tickets"))

    def test_unreadable_comments(self) -> None:
        """A comments file that is not the API's list is exit 2."""
        broken = write_text("broken.json", "[1]")
        code, err, written, _ = run(event(CITED), "--comments", broken)
        assert_that((code, written), equal_to((2, "")))
        assert_that(err, contains_string("broken.json"))


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
