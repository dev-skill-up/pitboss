"""The briefs say which nox check a worker runs, and that a Plan never names it."""

import unittest

from hamcrest import assert_that, equal_to

from .. import brief
from .briefmake import has_none, pinned, text
from .test_plan_commands import PLAN_REVIEWS

NOX = (
    "Nox: where the checks are nox sessions, run `timeout 598 pitboss nox` after"
    " each edit (the tests of one Python version first, then the skills, lint and"
    " mypy, each with `-r`, stopping at the first failure; module names after `--`"
    " run only those tests), and never the full `nox -r`: CI's `Run Nox` step runs"
    " the whole suite."
)
NOX_ORDER = (
    "Nox order: where the checks are nox sessions, run `nox -r -s tests-3.13`"
    " (one session) first and fix until it passes; only then run the other"
    " sessions (`lint`, `mypy`, `skills`), with `-r`. Never invoke `virtue` or"
    " `python -m virtue` by hand: the nox session is the way to run tests. Start"
    " nothing in the background that needs polling: use one foreground command"
    " under `timeout 598`, or one `Monitor` with an `until` loop."
)
FIRST_DESIGN = (
    "First design: throwing away a first design is acceptable and is not a thing"
    " to avoid; rewrite it when the tests show it is wrong."
)
PLAN_NO_NOX = (
    "CI evidence: the Plan never names `pitboss nox` or any nox run as its"
    " evidence (pitboss#179: a Plan asks for no evidence that CI shows); the whole"
    " suite is CI's `Run Nox` step, and the PR body points to it."
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
