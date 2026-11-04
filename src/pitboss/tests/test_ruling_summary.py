"""Tests for the daily summary of the Opus rulings and the owner's artifact (pitboss#237)."""

import datetime
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import roundline, rulingsummary, shapes, steps
from . import test_plan_revision, world
from .test_evidence_rules import read, words

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


def ruled(when: str, author: str = "MEMBER") -> shapes.Comment:
    """An Opus ruling comment.

    Args:
        when: when it was written.
        author: its author's association.

    Returns:
        The comment.
    """
    return shapes.Comment(body=RULING, author_association=author, created_at=when)


def swept(here: world.World) -> str:
    """What the sweep prints.

    Args:
        here: the world.

    Returns:
        The output.
    """
    return world.invoke(here, "sweep", here.config, *test_plan_revision.AFTER).out


class TestSweep(unittest.TestCase):
    """The sweep line, end to end."""

    def test_a_ruling_today_prints_the_line(self) -> None:
        """The line names the command that records the summary."""
        here = test_plan_revision.world_with(ruled(TODAY))
        first = swept(here)
        assert_that(first.count(MARK), equal_to(1))
        assert_that(first, contains_string(f"ruling-summary {here.config}"))

    def test_the_same_world_after_the_summary_is_recorded_prints_none(self) -> None:
        """The command records the Pacific day and the sweep is quiet."""
        here = test_plan_revision.world_with(ruled(TODAY))
        recorded = world.invoke(
            here, "ruling-summary", here.config, *test_plan_revision.AFTER
        )
        assert_that(recorded.out, contains_string("recorded the Opus ruling summary"))
        assert_that(swept(here).count(MARK), equal_to(0))

    def test_no_ruling_prints_no_line(self) -> None:
        """A PR with no ruling comment has nothing to summarize."""
        plain = shapes.Comment(
            body="LGTM", author_association="MEMBER", created_at=TODAY
        )
        here = test_plan_revision.world_with(plain)
        assert_that(swept(here).count(MARK), equal_to(0))


class TestDue(unittest.TestCase):
    """Which rulings wait for a summary."""

    now = moment("2030-01-01T09:00:00+00:00")

    def test_without_a_record_every_ruling_waits(self) -> None:
        """No summary was recorded yet."""
        found = rulingsummary.due([moment(TODAY)], "", self.now)
        assert_that(len(found), equal_to(1))

    def test_a_summary_of_the_pacific_day_clears_it(self) -> None:
        """01:00 UTC's next day is still the same Pacific day."""
        text = "2030-01-01T05:00:00+00:00\n"
        assert_that(rulingsummary.due([moment(TODAY)], text, self.now), equal_to([]))

    def test_a_summary_of_the_day_before_does_not(self) -> None:
        """A ruling after the last summary waits when the Pacific day changed."""
        text = "2030-01-01T07:00:00+00:00\n"
        later = moment("2030-01-01T08:30:00+00:00")
        found = rulingsummary.due([moment(TODAY), later], text, self.now)
        assert_that(found, equal_to([later]))

    def test_a_ruling_before_the_last_summary_does_not_wait(self) -> None:
        """Only the rulings dated since the last summary count."""
        text = "2029-12-30T10:00:00+00:00\n"
        old = moment("2029-12-30T09:00:00+00:00")
        assert_that(rulingsummary.due([old], text, self.now), equal_to([]))

    def test_a_line_that_cannot_be_read_is_skipped(self) -> None:
        """A cut line or a time with no offset is not a summary."""
        text = "2029-12-30\nnot a time\n2029-12-30T10:00:00"
        assert_that(rulingsummary.recorded(text), equal_to([]))


class TestRuledAt(unittest.TestCase):
    """When the rulings of a PR were written."""

    def test_only_trusted_rulings_with_a_time_count(self) -> None:
        """A stranger, a plain comment and an unreadable time are left out."""
        plain = shapes.Comment(
            body="LGTM", author_association="MEMBER", created_at=TODAY
        )
        comments = [ruled(TODAY), ruled(TODAY, author="NONE"), ruled("1"), plain]
        found = rulingsummary.ruled_at(comments, {"MEMBER"})
        assert_that(found, equal_to([moment(TODAY)]))


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

    def test_a_record_that_cannot_be_read_stops_the_command(self) -> None:
        """A directory cannot be read as the record."""
        here = world.make_world()
        with self.assertRaises(SystemExit):
            rulingsummary.note(here.clone, moment("2030-01-01T00:00:00+00:00"))

    def test_a_record_that_cannot_be_written_stops_the_command(self) -> None:
        """A file in a directory that is not there cannot be written."""
        here = world.make_world()
        path = here.clone / "missing" / "record.log"
        with self.assertRaises(SystemExit):
            rulingsummary.note(path, moment("2030-01-01T00:00:00+00:00"))


class TestEscalationCard(unittest.TestCase):
    """The step that has the orchestrator ask the owner says an artifact goes with it."""

    def test_the_sentence_is_pinned(self) -> None:
        """Each escalation step and its sweep line carry the sentence."""
        assert_that(steps.OWNER_ARTIFACT, equal_to(ARTIFACT))
        shown = [
            steps.TEXTS[steps.Step.PAUSE_FOR_OWNER],
            steps.TEXTS[steps.Step.RULING_ESCALATES],
            roundline.LINES[steps.Step.PAUSE_FOR_OWNER][1],
            roundline.LINES[steps.Step.RULING_ESCALATES][1],
        ]
        for text in shown:
            with self.subTest(text=text):
                assert_that(text, contains_string(ARTIFACT))


class TestRules(unittest.TestCase):
    """The rules file holds both halves of the ruling."""

    def test_the_bullet_has_both_halves(self) -> None:
        """The artifact for the owner's question and the daily summary."""
        found = words(read("rules.md"))
        assert_that([each for each in PHRASES if each not in found], equal_to([]))
