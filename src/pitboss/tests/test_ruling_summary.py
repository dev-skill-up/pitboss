"""Tests for the daily Opus ruling summary and the owner's artifact (pitboss#237)."""

import dataclasses
import datetime
import pathlib
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import rulingsummary, shapes
from . import blank, fakes, world
from .test_evidence_rules import read, words

AFTER = ("--now", world.FUTURE)
FEED = fakes.page("/".join([world.PROJECT, "issues", "comments"]))
MERGED_PR = "https://github.com/owner/project/pull/7#issuecomment-1"
CLOSED_ISSUE = "https://github.com/owner/project/issues/8#issuecomment-2"

NOW = datetime.datetime.fromisoformat("2030-01-01T09:00:00+00:00")
MARK = "OPUS RULINGS DAILY"
RULING = "Opus ruling\nRuling: do these steps\n"
TODAY = "2029-12-31T20:00:00Z"
ARTIFACT = (
    "attach a markdown artifact with the sections 'What happened',"
    " 'Recommendation' and 'Suggested mitigation'"
)
PHRASES = (
    "question that reaches the owner (a decision card, an escalation, a message"
    " that asks for a decision) comes with a markdown artifact with the sections"
    " `What happened`, `Recommendation` and `Suggested mitigation`",
    "the orchestrator summarizes every Opus ruling of the day, each with a"
    " suggested mitigation, as a markdown artifact",
)


def moment(text: str) -> datetime.datetime:
    """A time.

    Args:
        text: its ISO form.

    Returns:
        The time.
    """
    return datetime.datetime.fromisoformat(text)


def at(when: str, url: str = "") -> rulingsummary.Ruling:
    """A ruling.

    Args:
        when: its ISO time.
        url: its address.

    Returns:
        The ruling.
    """
    return rulingsummary.Ruling(when=moment(when), url=url)


def ruled(when: str, author: str = "MEMBER", url: str = "") -> shapes.Comment:
    """An Opus ruling comment.

    Args:
        when: when it was written.
        author: its author's association.
        url: its address.

    Returns:
        The comment.
    """
    return dataclasses.replace(
        blank.COMMENT, body=RULING, author_association=author, created_at=when, url=url
    )


def feed_with(*posted: shapes.Comment) -> world.World:
    """A world whose project's comment feed (every PR and issue) has comments.

    Args:
        *posted: the comments.

    Returns:
        The world.
    """
    here = world.make_world()
    here.bodies.update({FEED: list(map(world.comment_json, posted))})
    return here


def plain(when: str) -> shapes.Comment:
    """A comment that is no ruling.

    Args:
        when: when it was written.

    Returns:
        The comment.
    """
    return dataclasses.replace(
        blank.COMMENT, body="LGTM", author_association="MEMBER", created_at=when
    )


def ran(here: world.World, command: str) -> str:
    """What a command prints in a world.

    Args:
        here: the world.
        command: ``sweep`` or ``ruling-summary``.

    Returns:
        The output.
    """
    return world.invoke(here, command, here.config, *AFTER).out


def swept(here: world.World) -> str:
    """What the sweep prints, which has the line once or not at all.

    Args:
        here: the world.

    Returns:
        The output.
    """
    out = ran(here, "sweep")
    assert_that(out.count(MARK) <= 1, equal_to(True))
    return out


class TestSweep(unittest.TestCase):
    """The sweep line, end to end."""

    def test_a_ruling_today_prints_the_line(self) -> None:
        """The line names the command that records the summary."""
        first = swept(feed_with(ruled(TODAY)))
        assert_that(first, contains_string("`uvx pitboss ruling-summary "))

    def test_a_ruling_on_a_merged_pr_or_a_closed_issue_prints_the_line(self) -> None:
        """Neither is among the open PRs, and each ruling counts and is named."""
        for url in (MERGED_PR, CLOSED_ISSUE):
            with self.subTest(url=url):
                out = swept(feed_with(ruled(TODAY, url=url)))
                assert_that(
                    out, contains_string(f"{MARK}: 1 Opus ruling comment(s) ({url})")
                )

    def test_both_are_named_by_the_one_line(self) -> None:
        """The merged PR's ruling and the closed issue's are counted together."""
        out = swept(
            feed_with(ruled(TODAY, url=MERGED_PR), ruled(TODAY, url=CLOSED_ISSUE))
        )
        assert_that(
            out,
            contains_string(f"2 Opus ruling comment(s) ({MERGED_PR}, {CLOSED_ISSUE})"),
        )

    def test_the_same_world_after_the_summary_is_recorded_prints_none(self) -> None:
        """The command records the Pacific day and the sweep is quiet."""
        here = feed_with(ruled(TODAY, url=MERGED_PR), ruled(TODAY, url=CLOSED_ISSUE))
        assert_that(ran(here, "ruling-summary"), contains_string("recorded the Opus"))
        assert_that(MARK in swept(here), equal_to(False))

    def test_a_summary_of_an_earlier_day_asks_the_feed_since_then(self) -> None:
        """The comments asked for are the ones updated since the last summary."""
        here = feed_with()
        earlier = "2029-12-30T10:00:00+00:00\n"
        rulingsummary.record_path(here.clone).write_text(earlier, encoding="utf-8")
        query = "?since=2029-12-30T10:00:00Z"
        for repo, found in (
            (world.PROJECT, [ruled(TODAY, url=CLOSED_ISSUE)]),
            (world.LIBRARY, []),
        ):
            here.bodies[fakes.page(f"{repo}/issues/comments{query}")] = [
                world.comment_json(each) for each in found
            ]
        assert_that(swept(here), contains_string(CLOSED_ISSUE))

    def test_no_ruling_prints_no_line(self) -> None:
        """A comment that is no ruling has nothing to summarize."""
        assert_that(MARK in swept(feed_with(plain(TODAY))), equal_to(False))

    def test_a_feed_that_cannot_be_read_says_so(self) -> None:
        """The sweep does not stop; the line says which call failed."""
        here = feed_with()
        del here.bodies[FEED]
        out = swept(here)
        assert_that(out, contains_string(f"{MARK}: the Opus rulings cannot be counted"))
        assert_that(out, contains_string("the comments call failed (HTTP 404)"))


class TestDue(unittest.TestCase):
    """Which rulings wait for a summary."""

    def test_without_a_record_every_ruling_waits(self) -> None:
        """No summary was recorded yet."""
        found = rulingsummary.due([at(TODAY)], "", NOW)
        assert_that(len(found), equal_to(1))

    def test_a_summary_of_the_pacific_day_clears_it(self) -> None:
        """08:00 UTC is midnight Pacific, the same Pacific day as 09:00 UTC."""
        text = "2030-01-01T08:00:00+00:00\n"
        assert_that(rulingsummary.due([at(TODAY)], text, NOW), equal_to([]))

    def test_a_summary_of_the_day_before_does_not(self) -> None:
        """A ruling after the last summary waits when the Pacific day changed."""
        text = "2030-01-01T07:00:00+00:00\n"
        later = at("2030-01-01T08:30:00+00:00")
        found = rulingsummary.due([at(TODAY), later], text, NOW)
        assert_that(found, equal_to([later]))

    def test_a_ruling_before_the_last_summary_does_not_wait(self) -> None:
        """Only the rulings dated since the last summary count."""
        text = "2029-12-30T10:00:00+00:00\n"
        old = at("2029-12-30T09:00:00+00:00")
        assert_that(rulingsummary.due([old], text, NOW), equal_to([]))

    def test_the_feed_is_asked_since_the_last_summary_in_utc(self) -> None:
        """An offset becomes UTC; no record asks for everything."""
        text = "2029-12-29T00:00:00+00:00\n2029-12-30T02:00:00-08:00\n"
        assert_that(rulingsummary.since(text), equal_to("2029-12-30T10:00:00Z"))
        assert_that(rulingsummary.since(""), equal_to(""))

    def test_the_line_names_only_the_rulings_that_have_an_address(self) -> None:
        """A ruling with no address is counted and not named."""
        path = pathlib.Path("record.log")
        named = rulingsummary.line([at(TODAY, "u"), at(TODAY)], "cfg", path)
        assert_that(named, contains_string("2 Opus ruling comment(s) (u) on"))
        bare = rulingsummary.line([at(TODAY)], "cfg", path)
        assert_that(bare, contains_string("1 Opus ruling comment(s) on"))

    def test_a_line_that_cannot_be_read_is_skipped(self) -> None:
        """A cut line or a time with no offset is not a summary."""
        text = "2029-12-30\nnot a time\n2029-12-30T10:00:00"
        assert_that(rulingsummary.recorded(text), equal_to([]))


class TestRuledAt(unittest.TestCase):
    """When the rulings of a PR were written."""

    def test_only_trusted_rulings_with_a_time_count(self) -> None:
        """A stranger, a plain comment and an unreadable time are left out."""
        comments = [ruled(TODAY, url="u"), ruled(TODAY, author="NONE"), ruled("1")]
        comments.append(plain(TODAY))
        found = rulingsummary.ruled_at(comments, {"MEMBER"})
        assert_that(found, equal_to([at(TODAY, "u")]))


class TestNote(unittest.TestCase):
    """The record file."""

    def test_a_cut_last_line_gets_a_newline_first(self) -> None:
        """The new time is a line of its own."""
        here = world.make_world()
        path = rulingsummary.record_path(here.clone)
        path.write_text("2029-12-30T10:00:00+00:00", encoding="utf-8")
        rulingsummary.note(path, moment("2030-01-01T00:00:00+00:00"))
        assert_that(
            path.read_text(encoding="utf-8"),
            equal_to("2029-12-30T10:00:00+00:00\n2030-01-01T00:00:00+00:00\n"),
        )

    def test_a_record_that_cannot_be_used_stops_the_command(self) -> None:
        """A directory cannot be read as the record; a missing one cannot be written."""
        here = world.make_world()
        for path in (here.clone, here.clone / "missing" / "record.log"):
            with self.subTest(path=path), self.assertRaises(SystemExit):
                rulingsummary.note(path, NOW)


class TestRules(unittest.TestCase):
    """The rules file holds both halves of the ruling."""

    def test_the_bullet_has_both_halves(self) -> None:
        """The artifact for the owner's question and the daily summary."""
        found = words(read("rules.md"))
        assert_that([each for each in PHRASES if each not in found], equal_to([]))
