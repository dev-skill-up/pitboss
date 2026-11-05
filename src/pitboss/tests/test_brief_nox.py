"""The briefs say which nox check a worker runs, and that a Plan never names it."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import brief
from .briefmake import has_none, pinned, text
from .test_evidence_rules import read, words
from .test_plan_commands import PLAN_REVIEWS

NOX = (
    "Nox: where the checks are nox sessions, run `timeout 598 pitboss nox` after"
    " every edit and before every push, for iterating too (the tests of one Python"
    " version first, then the skills, lint and mypy; it stops at the first failure"
    " and always uses `-r`); a targeted test module, `nox -s ...` or `virtue` is"
    " never run by hand, and never the full `nox -r`: CI's `Run Nox` step runs the"
    " whole suite."
)
NOX_ORDER = (
    "Nox order: where the checks are nox sessions, never invoke `virtue` or"
    " `python -m virtue` by hand: the nox session is the way to run tests. Start"
    " nothing in the background that needs polling: use one foreground command"
    " under `timeout 598`, or one `Monitor` with an `until` loop."
)
HAND_BACK_NOX = (
    " and, where the checks are nox sessions, the `pitboss nox` result of the"
    " pushed head (the four sessions and their status); nothing else."
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

    def test_the_sentence_is_once_in_the_sweep_skill_references(self) -> None:
        """The same sentence is once in rules.md (pitboss#250)."""
        assert_that(words(read("rules.md")).count(NOX), equal_to(1))

    def test_every_worker_brief_asks_for_the_nox_result_of_the_head(self) -> None:
        """The hand-back names the four sessions and their status (pitboss#250)."""
        for kind in WORKERS:
            pinned(kind, [HAND_BACK_NOX])

    def test_the_reference_has_the_hand_back_check_for_the_nox_result(self) -> None:
        """The check of a hand-back names a missing `pitboss nox` result."""
        rule = (
            "a hand-back without the `pitboss nox` result of the pushed head"
            " (the four sessions and their status) is sent back, naming it as"
            " missing"
        )
        assert_that(words(read("rules.md")), contains_string(rule))

    def test_every_worker_brief_orders_the_sessions_and_forbids_polling(self) -> None:
        """One session first, no virtue by hand, nothing to poll (pitboss#175)."""
        for kind in WORKERS:
            pinned(kind, [NOX_ORDER])

    def test_the_order_applies_only_where_the_checks_are_nox_sessions(self) -> None:
        """Like the Nox sentence, the order is conditional (pitboss#175)."""
        assert_that(NOX.startswith("Nox: where the checks"), equal_to(True))
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
