"""Rows whose own tests missed a mutant: each runs the test that kills it.

The keyword is mutation-check. The name of a test carries the row id; the test it runs
is the existing guard of the behaviour the mutant changes.
"""

import unittest

from .killers import rerun


class TestRowsHoldTheirFunctions1(unittest.TestCase):
    """Mutants an existing test of another module kills, part 1."""

    def test_a1_plan_edited_without_ruling_1_is_held_by_a_test_of_its_behaviour(
        self,
    ) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: False -> True.
        """
        rerun(
            "pitboss.tests.test_body_only_round",
            "TestBodyOnlyRound",
            "test_a_clean_check_of_another_plan_gives_the_fix",
        )

    def test_a1_plan_edited_without_ruling_2_is_held_by_a_test_of_its_behaviour(
        self,
    ) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: each.author_association in pr.trusted -> each.author_asso.
        """
        rerun(
            "pitboss.tests.test_current_for",
            "TestPairs",
            "test_c31_a_revised_plan_after_a_ruling_is_reviewed_again_after_a_push",
        )

    def test_a3_checked_since_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: newest and (not unchecked(pr)) -> newest or not unchecked.
        """
        rerun(
            "pitboss.tests.test_body_only_round",
            "TestBodyOnlyRound",
            "test_t462_a_refusal_after_the_ruling_gives_the_fix",
        )

    def test_a4_next_step_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: step.step in steps.HELD -> step.step not in steps.HELD.
        """
        rerun(
            "pitboss.tests.test_body_only_round",
            "TestStepReview",
            "test_a_pr_at_another_step_is_refused",
        )

    def test_a10_next_step_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: step.step in steps.HELD -> step.step not in steps.HELD.
        """
        rerun(
            "pitboss.tests.test_body_only_round",
            "TestStepReview",
            "test_a_pr_at_another_step_is_refused",
        )

    def test_a11_refusal_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: newest is not None and needs_check(body, comments, trusted).
        """
        rerun(
            "pitboss.tests.test_base_check",
            "TestTheCommand",
            "test_a_base_the_head_equals_fails_the_check_naming_the_test",
        )

    def test_a16_ci_gate_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: ci is Ci.RED -> ci is not Ci.RED.
        """
        rerun(
            "pitboss.tests.test_body_only_round",
            "TestBodyOnlyRound",
            "test_a_clean_check_of_another_plan_gives_the_fix",
        )

    def test_a16_ci_gate_2_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: waiting_step(pr, review) or steps.worker(steps.Task.FIX_CI).
        """
        rerun(
            "pitboss.tests.test_clean_waits",
            "TestCleanWaits",
            "test_a_clean_pr_at_a_wait_prints_the_wait_and_no_next_line",
        )

    def test_a16_ci_gate_3_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: review is None -> review is not None.
        """
        rerun(
            "pitboss.tests.test_body_edits",
            "TestTheBodyAtAMark",
            "test_a_mark_where_the_body_then_differs_from_the_final_one",
        )

    def test_a16_ci_gate_4_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: unfixed_execution(pr) or plancheckflow.execution_review(pr,.
        """
        rerun(
            "pitboss.tests.test_flow",
            "TestBranches",
            "test_a_plan_approved_in_a_draft_is_carried_to_the_execution_review",
        )

    def test_a16_ci_gate_5_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: flowstate.plan_rejected_last(pr) or plan_revised(pr) -> f.
        """
        rerun(
            "pitboss.tests.test_no_drafts_review",
            "TestFlow",
            "test_a_revised_plan_is_reviewed_with_the_execution",
        )

    def test_a17_build_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: spec.kind is Kind.RULING -> spec.kind is not Kind.RULING.
        """
        rerun(
            "pitboss.tests.test_all_findings",
            "TestSweep",
            "test_pause_counts_the_findings_marked_missed_earlier",
        )

    def test_a18_refusal_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: rest not in NOTHING and (not IMPOSSIBLE.search(handback)) .
        """
        rerun(
            "pitboss.tests.test_base_check",
            "TestTheCommand",
            "test_a_base_the_head_equals_fails_the_check_naming_the_test",
        )


class TestRowsHoldTheirFunctions2(unittest.TestCase):
    """Mutants an existing test of another module kills, part 2."""

    def test_a23_build_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: spec.kind is Kind.RULING -> spec.kind is not Kind.RULING.
        """
        rerun(
            "pitboss.tests.test_all_findings",
            "TestSweep",
            "test_pause_counts_the_findings_marked_missed_earlier",
        )

    def test_a25_findings_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: 80 -> 81.
        """
        rerun(
            "pitboss.tests.test_holdwait",
            "TestShippedTexts",
            "test_the_skill_says_it_in_one_place",
        )

    def test_a29_only_pins_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: name in pin_files -> name not in pin_files.
        """
        rerun(
            "pitboss.tests.test_pins_verify",
            "TestReading",
            "test_only_pins",
        )

    def test_b13_overdue_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: elapsed <= datetime.timedelta(minutes=OVERDUE_MINUTES) -> .
        """
        rerun(
            "pitboss.tests.test_check_in",
            "TestCheckIn",
            "test_next_and_sweep_by_minutes",
        )

    def test_b19_findings_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: not _NEGATED.search(each) -> _NEGATED.search(each).
        """
        rerun(
            "pitboss.tests.test_holdwait",
            "TestShippedTexts",
            "test_the_skill_says_it_in_one_place",
        )

    def test_b26_stale_heads_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: head and produced(each) and each.in_evidence -> head or p.
        """
        rerun(
            "pitboss.tests.test_evidence_head",
            "TestFindings",
            "test_no_head_judges_nothing",
        )

    def test_c3_remove_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: each.worktree.branch == branch and each.reason in local.MER.
        """
        rerun(
            "pitboss.tests.test_worktrees",
            "TestMerged",
            "test_another_branch_is_not_touched",
        )

    def test_c5_settle_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: False -> True.
        """
        rerun(
            "pitboss.tests.test_supersede",
            "TestSettle",
            "test_another_run_of_the_same_workflow_answers",
        )

    def test_c6_unmarked_line_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: not globs or marked(tree, globs, ticket) -> not globs and.
        """
        rerun(
            "pitboss.tests.test_default_config",
            "TestCommandsWithAConfiguration",
            "test_every_command_with_a_configuration_is_run_here",
        )

    def test_c10_lines_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: ours is None or theirs is None or ours >= theirs -> ours .
        """
        rerun(
            "pitboss.tests.test_config",
            "TestExample",
            "test_example_loads",
        )

    def test_i15_next_step_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: step.step in steps.HELD -> step.step not in steps.HELD.
        """
        rerun(
            "pitboss.tests.test_body_only_round",
            "TestStepReview",
            "test_a_pr_at_another_step_is_refused",
        )

    def test_i16_ordered_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: item.category is Category.RELOCK_REVIEW -> item.category .
        """
        rerun(
            "pitboss.tests.test_slots_rules",
            "TestRelockLast",
            "test_b9_a_relock_review_is_last",
        )

    def test_i16_ordered_2_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: item.category is Category.NEW_PR -> item.category is not .
        """
        rerun(
            "pitboss.tests.test_closing_comment",
            "TestSlotsNext",
            "test_every_blocker_has_merged",
        )


class TestRowsHoldTheirFunctions3(unittest.TestCase):
    """Mutants an existing test of another module kills, part 3."""

    def test_i18_classify_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: 2 -> 3.
        """
        rerun(
            "pitboss.tests.test_nox_coverage",
            "TestChangedCoverage",
            "test_the_uncovered_line_is_refused_and_the_covering_test_passes",
        )

    def test_i27_stale_heads_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: head and produced(each) and each.in_evidence -> head or p.
        """
        rerun(
            "pitboss.tests.test_evidence_head",
            "TestFindings",
            "test_no_head_judges_nothing",
        )

    def test_i36_holder_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: slot.started or 'unknown' -> slot.started and 'unknown'.
        """
        rerun(
            "pitboss.tests.test_leak",
            "TestScratch",
            "test_a_directory_is_fresh_unless_the_process_owns_it",
        )

    def test_i38_lines_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: each.finished and each.succeeded -> each.finished or each.
        """
        rerun(
            "pitboss.tests.test_config",
            "TestExample",
            "test_example_loads",
        )

    def test_t475_next_step_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: step.step in steps.HELD -> step.step not in steps.HELD.
        """
        rerun(
            "pitboss.tests.test_body_only_round",
            "TestStepReview",
            "test_a_pr_at_another_step_is_refused",
        )

    def test_t417_build_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: spec.kind is Kind.RULING -> spec.kind is not Kind.RULING.
        """
        rerun(
            "pitboss.tests.test_all_findings",
            "TestSweep",
            "test_pause_counts_the_findings_marked_missed_earlier",
        )

    def test_t419_missing_line_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: each not in known.kinds -> each in known.kinds.
        """
        rerun(
            "pitboss.tests.test_done_when",
            "TestDoneWhenNames",
            "test_each_missing_name_is_named",
        )

    def test_t52_findings_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: path.suffix not in SUFFIXES or not path.is_file() -> path.
        """
        rerun(
            "pitboss.tests.test_holdwait",
            "TestShippedTexts",
            "test_the_skill_says_it_in_one_place",
        )

    def test_t53_fields_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: spec.kind is Kind.NEW_PR -> spec.kind is not Kind.NEW_PR.
        """
        rerun(
            "pitboss.tests.test_brief_order",
            "TestOrderTables",
            "test_the_rule_sits_in_the_tickets_section_of_rules",
        )

    def test_c30_findings_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: 120 -> 121.
        """
        rerun(
            "pitboss.tests.test_holdwait",
            "TestShippedTexts",
            "test_the_skill_says_it_in_one_place",
        )

    def test_c34_findings_1_is_held_by_a_test_of_its_behaviour(self) -> None:
        """A mutant of the row is killed by the test it reruns.

        The mutant: 60 -> 61.
        """
        rerun(
            "pitboss.tests.test_holdwait",
            "TestShippedTexts",
            "test_the_skill_says_it_in_one_place",
        )
