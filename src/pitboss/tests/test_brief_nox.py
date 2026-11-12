"""The briefs say which nox check a worker runs, and that a Plan never names it."""

import unittest

from hamcrest import assert_that, equal_to, starts_with

from .. import brief, nox_commands
from .briefmake import pinned, text
from .says import has_none
from .briefmake import PLAN_REVIEWS

NOX = (
    "Nox: where the checks are nox sessions, run `timeout 598 pitboss nox` before"
    " a push, at most once per head, after the last edit (a maximum, not a"
    " target; the skills, lint and"
    " mypy first, then the tests of one Python version, which stop at the first"
    " failing test; it stops at the first failing session and always uses `-r`); a"
    " targeted test module, `nox -s ...` or `virtue` is never run by hand,"
    " and never the full `nox -r`: CI's `Run Nox` step runs the whole suite."
)
NOX_ORDER = (
    "Nox order: where the checks are nox sessions, never invoke `virtue` or"
    " `python -m virtue` by hand: the nox session is the way to run tests. Start"
    " nothing in the background that needs polling: use one foreground command"
    " under `timeout 598`, or one `Monitor` with an `until` loop."
)
HAND_BACK_NOX = (
    " and, where the checks are nox sessions, the `pitboss nox` result of the"
    " pushed head (the four sessions and their status),"
)
FIRST_DESIGN = (
    "First design: throwing away a first design is acceptable and is not a thing"
    " to avoid; rewrite it when the tests show it is wrong."
)
PLAN_NO_NOX = (
    "CI evidence: the Plan never names `pitboss nox` or any nox run as its"
    " evidence (pitboss#179: a Plan asks for no evidence that CI shows); the whole"
    " suite is CI's `Run Nox` step, which the Plan points to as the CI pointer"
    " rule says."
)
PLAN_NO_NOX_REVIEW = (
    "CI evidence: a Plan that names `pitboss nox` or any nox run as its evidence"
    " is changes needed (pitboss#179: a Plan asks for no evidence that CI shows);"
    " the whole suite is CI's `Run Nox` step."
)
WORKERS = (
    brief.Kind.NEW_PR,
    brief.Kind.FIRST_ROUND,
    brief.Kind.REVISE_PLAN,
    brief.Kind.FIX_REVIEW,
    brief.Kind.FIX_CI,
    brief.Kind.RESOLVE_CONFLICT,
)
PLAN_WRITERS = WORKERS[:4]


class TestNoxInTheBriefs(unittest.TestCase):
    """The worker runs `pitboss nox`; a Plan names no nox run (pitboss#210)."""

    def test_every_worker_brief_names_the_local_check(self) -> None:
        """The sentence is pinned in each worker brief."""
        for kind in WORKERS:
            pinned(kind, [NOX])

    def test_the_sentence_says_before_each_push_and_never_after_every_edit(
        self,
    ) -> None:
        """The owner never said after every edit (pitboss#345)."""
        for kind in brief.Kind:
            assert_that("after every edit" in text(kind), equal_to(False))
        assert_that("at most once per head, after the last edit" in NOX, equal_to(True))
        assert_that("after every edit" in NOX, equal_to(False))

    def test_the_command_text_never_says_after_every_edit(self) -> None:
        """No help text of the command says it either."""
        assert_that(
            "after every edit" in (nox_commands.nox.__doc__ or ""), equal_to(False)
        )

    def test_every_worker_brief_asks_for_the_nox_result_of_the_head(self) -> None:
        """The hand-back names the four sessions and their status (pitboss#250)."""
        for kind in WORKERS:
            pinned(kind, [HAND_BACK_NOX])

    def test_every_worker_brief_orders_the_sessions_and_forbids_polling(self) -> None:
        """One session first, no virtue by hand, nothing to poll (pitboss#175)."""
        for kind in WORKERS:
            pinned(kind, [NOX_ORDER])

    def test_the_order_applies_only_where_the_checks_are_nox_sessions(self) -> None:
        """Like the Nox sentence, the order is conditional (pitboss#175)."""
        assert_that(NOX, starts_with("Nox: where the checks"))
        assert_that(
            NOX_ORDER.startswith("Nox order: where the checks are nox sessions"),
            equal_to(True),
        )

    def test_every_worker_brief_allows_a_thrown_away_first_design(self) -> None:
        """Discarding a first design is no failure (pitboss#175)."""
        for kind in WORKERS:
            pinned(kind, [FIRST_DESIGN])
        has_none(text(brief.Kind.REVIEW_EXECUTION), [FIRST_DESIGN, NOX_ORDER])

    def test_a_plan_writing_brief_forbids_a_nox_run_as_evidence(self) -> None:
        """The worker's sentence under the CI-evidence rule."""
        for kind in PLAN_WRITERS:
            pinned(kind, [PLAN_NO_NOX])
        has_none(text(brief.Kind.FIX_CI), [PLAN_NO_NOX])

    def test_a_plan_review_brief_makes_a_nox_run_changes_needed(self) -> None:
        """The reviewer's sentence under the CI-evidence rule."""
        for kind in PLAN_REVIEWS:
            pinned(kind, [PLAN_NO_NOX_REVIEW])
        has_none(text(brief.Kind.REVIEW_EXECUTION), [PLAN_NO_NOX_REVIEW])
