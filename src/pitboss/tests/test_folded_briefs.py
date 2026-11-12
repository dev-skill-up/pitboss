"""The sentences the folded tickets asked of the briefs (pitboss#444, item 6)."""

import unittest


from .. import brief
from .briefmake import has_all, has_none, text

WORKERS = (brief.Kind.NEW_PR, brief.Kind.FIRST_ROUND, brief.Kind.REVISE_PLAN)
EXECUTIONS = (brief.Kind.REVIEW_FULL, brief.Kind.REVIEW_EXECUTION)


class TestFoldedBriefs(unittest.TestCase):
    """A worker brief or a review brief carries each sentence."""

    def test_t407_the_worker_plans_one_input_for_each_spelling(self) -> None:
        """Every worker that writes a Plan is told to list and plant each spelling."""
        for kind in WORKERS:
            has_all(
                text(kind),
                [
                    "a new or changed check that reads Python syntax (an `ast`"
                    " scan) lists, in the Plan, each spelling of every form the"
                    " Done-when names",
                    "`from m import f [as g]`",
                    "`async def`, `lambda`",
                    "plants one input for each in the scan's test file",
                ],
            )

    def test_t407_the_review_refuses_a_scan_missing_a_spelling(self) -> None:
        """The Execution review: a spelling with no planted input is changes needed."""
        for kind in EXECUTIONS:
            has_all(
                text(kind),
                [
                    "a new syntax scan whose test file lacks a planted input for"
                    " a spelling of a form the Done-when names is changes needed,"
                    " with the spelling named"
                ],
            )
        has_none(text(brief.Kind.NEW_PR), ["is changes needed, with the spelling"])

    def test_t417_a_scheduling_constraint_is_not_an_impossibility(self) -> None:
        """The review refuses a deviation whose reason is a queue or a slot."""
        for kind in EXECUTIONS:
            has_all(
                text(kind),
                [
                    "a deviation from a Done-when item is accepted only when the"
                    " Plan or the Execution demonstrates that the item cannot be"
                    " met as written",
                    "a queue, a slot, an order or `one PR at a time`",
                    "refused with `Verdict: changes needed`",
                ],
            )

    def test_t285_the_design_has_a_guarantee_table_and_a_lifecycle_list(self) -> None:
        """The worker writes both tables; the review checks each row."""
        has_all(
            text(brief.Kind.NEW_PR),
            [
                "a row naming the function, the file and the test (static reject"
                " or dynamic) that enforce it",
                "a lifecycle list: how it is created, upgraded, read, deleted,"
                " restored and cleaned up",
                "re-checks every code path its own additions touch, not only the"
                " finding's text",
            ],
        )
        for kind in (brief.Kind.REVIEW_FULL, brief.Kind.REVIEW_PLAN):
            has_all(
                text(kind),
                [
                    "check each row of its guarantee table against the code",
                    "every caller of the primitive",
                ],
            )

    def test_t286_a_path_outside_the_checkout_needs_its_state_in_the_plan(
        self,
    ) -> None:
        """Worker and Plan review: the state a scratch command reads, and a limit."""
        has_all(
            text(brief.Kind.NEW_PR),
            [
                "a path outside the checkout needs, in the Plan, the precise"
                " commands that make that path or rows that show the state the"
                " command reads",
                "states every step the script runs before the measured one",
                "gives the measured time, N and the margin",
            ],
        )
        has_all(
            text(brief.Kind.REVIEW_PLAN),
            [
                "a Plan row that runs in, or reads, a path that no earlier row"
                " makes or shows is changes needed",
                "from a fresh scratch directory made only from the Plan's strings",
            ],
        )

    def test_t447_the_relock_review_has_the_test_fix_case(self) -> None:
        """A test file beside the pins is the case; a source file is still refused."""
        has_all(
            text(brief.Kind.REVIEW_RELOCK),
            [
                "`a test fix that the new pin needs`",
                "exactly the named test files",
                "a measured maximum plus a stated margin for a budget",
                "`Override:`-free verdict",
                "each run's id as a link and its measured numbers, the maximum,"
                " and the margin chosen over it with its reason",
                "A source file beside the pins is still changes needed",
                "a source, test or doc change is changes needed",
            ],
        )

    def test_t221_the_revised_plan_pushes_nothing(self) -> None:
        """No brief tells an agent to push an empty commit; the Head line stays."""
        for kind in brief.Kind:
            has_none(
                text(kind),
                ["git commit --allow-empty", "end with an empty commit"],
            )
        has_all(
            text(brief.Kind.REVISE_PLAN),
            ["push nothing, leave the `Head:` line as it is, and hand back the body"],
        )


class TestDraftCi(unittest.TestCase):
    """The sentence about a draft's CI is the one that is still true (pitboss#321)."""

    def test_t321_a_draft_runs_no_job_and_its_check_is_skipped(self) -> None:
        """Skipped, not missing; the old claim that a draft has no check run is gone."""
        for kind in (brief.Kind.REVIEW_PLAN, brief.Kind.REVIEW_FULL):
            found = text(kind, ready=False)
            has_none(found, ["a draft has no check run"])
        has_all(
            text(brief.Kind.REVIEW_PLAN, ready=False),
            [
                "a draft runs no CI job (its check is reported skipped, never"
                " missing; keyword: draft-ci, pitboss#321)",
                "never hand back `NOT STARTED` for a missing check run of a draft",
            ],
        )
