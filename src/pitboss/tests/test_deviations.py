"""The hand-back has a ``Deviations:`` line (keyword: deviations, pitboss#257)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, brieftextnote, brieftextwork, deviations
from . import world
from .briefmake import text
from .handbackrun import saved
from .handbackworld import ready
from .test_evidence_rules import words
from .says import ended

EXECUTION_REVIEWS = {brief.Kind.REVIEW_FULL, brief.Kind.REVIEW_EXECUTION}
WORKERS = (
    brief.Kind.NEW_PR,
    brief.Kind.FIRST_ROUND,
    brief.Kind.REVISE_PLAN,
    brief.Kind.FIX_REVIEW,
    brief.Kind.FIX_ROUND,
    brief.Kind.FIX_CI,
    brief.Kind.RESOLVE_CONFLICT,
    brief.Kind.RULING_STEPS,
    brief.Kind.RULING_AS_GIVEN,
    brief.Kind.RUN_PLAN,
    brief.Kind.ADD_CI_QUOTES,
)
ASKS = brieftextwork.DEVIATIONS
READS = brieftextnote.DEVIATIONS_REVIEW
HAND_BACK_NAMES = (
    "and the `Deviations:` line (only a departure from the Plan's commands or the"
    " ticket's Done-when, or `none`); nothing else."
)
HARMLESS = (
    "PR 5\nhead abc\nI wrote one file with a heredoc, edited another with"
    " `sed`, ran in a virtualenv, redirected nox output to a file and made a"
    " research fetch.\n"
    "Deviations: none\n"
)
WITH_LINE = "PR 5\nhead abc\nDeviations: two `sed -i` runs, one `rm`\n"
WITH_NONE = "PR 5\nhead abc\nDeviations: none\n"
WITHOUT_LINE = "PR 5\nhead abc\nI used the Edit tool.\n"
EMPTY_LINE = "PR 5\nDeviations:\n"


class TestTheBriefs(unittest.TestCase):
    """A worker is asked for the line, a reviewer reads it."""

    def test_every_worker_brief_asks_for_the_line_before_the_hand_back(self) -> None:
        """Each worker brief asks for it and its Hand-back names it; no review does."""
        for kind in WORKERS:
            found = text(kind)
            assert_that(found, contains_string(ASKS))
            assert_that(found.index(ASKS) < found.index("Hand-back:"), equal_to(True))
            hand_back = found[found.index("Hand-back:") :].split("\n")[0]
            assert_that(hand_back, contains_string(HAND_BACK_NAMES))
        for kind in EXECUTION_REVIEWS:
            assert_that(ASKS in text(kind), equal_to(False))

    def test_the_sentence_says_a_hand_back_without_it_is_not_started(self) -> None:
        """The orchestrator sends it back."""
        assert_that(
            ASKS,
            contains_string("a hand-back without it is NOT STARTED and is sent back"),
        )

    def test_the_review_of_an_execution_reads_the_line_and_records_it(self) -> None:
        """Only what cost something is a finding; a harmless habit never fails."""
        for kind in EXECUTION_REVIEWS:
            assert_that(text(kind), contains_string(READS))
        for kind in (brief.Kind.REVIEW_PLAN, brief.Kind.REVIEW_FIX_ROUND):
            assert_that(READS in text(kind), equal_to(False))
        for part in (
            "a departure from the Plan's commands or the ticket's Done-when",
            "`pitboss nox` run more than once on one head is one",
            "a trace in the tree that the Edit tool would not have",
            "how a file is edited (a heredoc, the Edit tool, `sed`)",
            "is never a deviation and never fails a PR",
            "for the sweep's ledger line for the worker",
        ):
            assert_that(READS, contains_string(part))

    def test_the_sentence_names_only_a_departure_from_the_plan_or_the_done_when(
        self,
    ) -> None:
        """How a file is edited, a virtualenv, a file or a fetch is never one."""
        for part in (
            "only a departure from the Plan's commands or the ticket's Done-when",
            "`pitboss nox` run more than once on one head is one",
            "how a file is edited (a heredoc, the Edit tool, `sed`), a virtualenv,"
            " a redirected output file or a research fetch is never a deviation",
            "`Deviations: none` beside them",
        ):
            assert_that(words(ASKS), contains_string(part))
        for gone in ("costs something", "rule of the owner"):
            for each in (ASKS, READS, deviations.NOT_STARTED, HAND_BACK_NAMES):
                assert_that(gone in each, equal_to(False))


def checked(text: str) -> world.Result:
    """Run ``hand-back-check`` on a hand-back in a world with the PR of its branch.

    Args:
        text: the hand-back.

    Returns:
        What it printed and its status.
    """
    here = ready(world.make_world())
    return world.invoke(here, "hand-back-check", saved(text), "--config", here.config)


class TestTheHandBack(unittest.TestCase):
    """A hand-back with and without the line."""

    def test_the_line_is_read_with_its_text(self) -> None:
        """What follows the prefix, stripped; nothing for no line."""
        assert_that(deviations.line(WITH_LINE), equal_to("two `sed -i` runs, one `rm`"))
        assert_that(deviations.line(WITH_NONE), equal_to("none"))
        assert_that(deviations.line(WITHOUT_LINE), equal_to(""))
        assert_that(deviations.line(EMPTY_LINE), equal_to(""))

    def test_a_hand_back_that_lists_none_of_the_harmless_habits_is_accepted(
        self,
    ) -> None:
        """A heredoc or `sed` edit, a virtualenv, a file or a fetch: `none`."""
        assert_that(deviations.not_started(HARMLESS), equal_to(""))
        found = checked(HARMLESS)
        ended(found, 0, "ok\n")

    def test_without_the_line_it_is_not_started(self) -> None:
        """Only a line that says something passes."""
        assert_that(deviations.not_started(WITH_LINE), equal_to(""))
        assert_that(deviations.not_started(WITH_NONE), equal_to(""))
        for each in (WITHOUT_LINE, EMPTY_LINE):
            assert_that(deviations.not_started(each), equal_to(deviations.NOT_STARTED))
            assert_that(deviations.NOT_STARTED, contains_string("NOT STARTED"))

    def test_the_command_prints_ok_or_the_text_and_exits_1(self) -> None:
        """The orchestrator's check of a hand-back saved in a file."""
        expected = {
            WITH_LINE: [0, "ok\n"],
            WITH_NONE: [0, "ok\n"],
            WITHOUT_LINE: [1, deviations.NOT_STARTED + "\n"],
        }
        for handback, wanted in expected.items():
            done = checked(handback)
            assert_that([done.code, done.out], equal_to(wanted))


REVIEW = (
    "Verdict: approved\n"
    "Deviation: two `sed -i` runs, no trace in the tree\n"
    "Deviation: one `rm`, a backup file left\n"
    "Deviation: none\n"
    "Deviations: not a review line\n"
)


LATER = (
    "Verdict: approved\n"
    "Deviation: two `sed -i` runs, no trace in the tree\n"
    "Deviation: one python heredoc, no trace in the tree\n"
)
LINES = [
    "deviation owner/project#9: two `sed -i` runs, no trace in the tree",
    "deviation owner/project#9: one `rm`, a backup file left",
]
NEW_LINE = "deviation owner/project#9: one python heredoc, no trace in the tree"


class TestTheLedger(unittest.TestCase):
    """A review's ``Deviation:`` lines end up in the ledger line of the worker."""

    def test_the_lines_of_a_review_are_read(self) -> None:
        """Only the lines with the review prefix, and not ``none``."""
        assert_that(
            deviations.recorded(REVIEW),
            equal_to(
                [
                    "two `sed -i` runs, no trace in the tree",
                    "one `rm`, a backup file left",
                ]
            ),
        )
        assert_that(deviations.recorded("Verdict: approved\n"), equal_to([]))

    def test_slots_deviation_records_them_once_and_keeps_them_after_free(self) -> None:
        """A repeat records nothing new, and the lines outlive the slot."""
        here, review = world.make_world(), saved(REVIEW)
        steps = (
            ("set", "tiny", "agent-1", "#9", "--running", "agent-1"),
            ("deviation", "#9", review),
            ("show",),
            ("deviation", "#9", review),
            ("free", "tiny", "--done", "agent-1"),
            ("show",),
        )
        seen = []
        for action, *rest in steps:
            done = world.invoke(here, "slots", action, here.config, *rest)
            held = [text for text in done.out.splitlines() if text in LINES]
            seen.append((done.code, held, done.out.splitlines()[-2:] == LINES))
        shown = (0, LINES, True)
        freed = (0, LINES, False)
        assert_that(seen, equal_to([(0, [], False), *[shown] * 3, freed, shown]))

    def test_a_new_line_of_a_later_review_is_added_after_the_others(self) -> None:
        """The old lines first, then the new one."""
        here = world.make_world()
        outputs = [
            world.invoke(here, "slots", "deviation", here.config, "#9", saved(text))
            for text in (REVIEW, LATER)
        ]
        found = [each for each in outputs[-1].out.splitlines() if "#9:" in each]
        assert_that(found, equal_to([*LINES, NEW_LINE]))

    def test_a_missing_review_file_is_refused(self) -> None:
        """Nothing is recorded."""
        here = world.make_world()
        gone = world.invoke(here, "slots", "deviation", here.config, "#7", "/none")
        assert_that(f"{gone.code} {gone.err}", contains_string("\nrefused: /none"))
