"""The rules of the register that code and tests already held (pitboss#444, item 2).

Each test here is named for the id of a rule of ``rules.tsv`` and runs the
existing tests that show the rule on its real function, so the register names a
test with the id in it. ``shown`` runs every test method of that name in a module.
"""

import importlib
import unittest
from typing import Sequence

from hamcrest import assert_that, greater_than_or_equal_to


def shown(module: str, *names: str) -> int:
    """Run the named tests of a test module.

    Args:
        module: the test module, ``test_flow``.
        *names: the test methods.

    Returns:
        How many methods ran; each raises on failure.
    """
    loaded = importlib.import_module(f"pitboss.tests.{module}")
    ran = 0
    for wanted in names:
        for each in vars(loaded).values():
            if isinstance(each, type) and issubclass(each, unittest.TestCase):
                if each is not unittest.TestCase and wanted in vars(each):
                    each(wanted).debug()
                    ran += 1
    return ran


def each(module: str, names: Sequence[str]) -> None:
    """Run the tests of a module.

    Args:
        module: the test module.
        names: the test methods.
    """
    assert_that(shown(module, *names), greater_than_or_equal_to(len(names)))


class TestOrder(unittest.TestCase):
    """The rules about the order of a PR (A)."""

    def test_a10_plan_rejection_fix_then_ruling_then_owner(self) -> None:
        """First rejection the fix, second the ruling, then the owner."""
        each(
            "test_flow",
            [
                "test_plan_rejected_the_first_time",
                "test_plan_rejected_the_second_time",
                "test_plan_rejected_after_an_opus_ruling",
            ],
        )

    def test_a11_a_refused_plan_check_is_the_workers_fix(self) -> None:
        """The refusal goes back to the worker with its findings."""
        each(
            "test_plan_check_step",
            ["test_a_refusal_of_this_plan_is_the_fix_with_its_findings"],
        )

    def test_a12_no_review_or_ready_before_a_clean_plan_check(self) -> None:
        """A draft or a ready PR waits for the check, then is offered."""
        each(
            "test_plan_check_step",
            ["test_a_clean_check_of_this_plan_offers_the_review"],
        )

    def test_a13_a_plan_command_is_run_as_written(self) -> None:
        """The exploration command in its place is a finding."""
        each(
            "test_plan_command_lint",
            ["test_each_case", "test_the_line_is_the_one_the_ticket_asks_for"],
        )

    def test_a14_a_plan_row_names_the_whole_command(self) -> None:
        """A row that is not the Evidence line's whole command is a finding."""
        each("test_plan_row", ["test_each_case"])

    def test_a15_ci_evidence_is_a_pointer(self) -> None:
        """A row has a command, a read or a CI pointer."""
        each("test_plan_pointer", ["test_each_case"])

    def test_a16_the_execution_review_waits_for_ci(self) -> None:
        """Nothing runs until the head's CI finishes."""
        each("test_flow", ["test_nothing_runs_until_ci_finishes"])

    def test_a18_a_partial_hand_back_needs_the_impossible_line(self) -> None:
        """The hand-back is refused without the demonstration."""
        each(
            "test_worker_rules",
            ["test_b17_a_partial_hand_back_without_impossible_is_refused"],
        )


class TestReviews(unittest.TestCase):
    """The rules about reviews, plans and bodies (A, second part)."""

    def test_a21_a_pr_closing_several_tickets_needs_a_ruling(self) -> None:
        """Folded tickets are allowed only by a recorded ruling."""
        each("test_folds", ["test_allows", "test_closes_counts"])

    def test_a22_an_approved_plan_is_not_judged_again(self) -> None:
        """Only an approval of this Plan counts, and the row rules skip it."""
        each("test_plan_approved", ["test_only_an_approval_of_this_plan_counts"])
        each("test_plan_pointer", ["test_an_approved_plan_is_not_judged"])

    def test_a23_a_review_lists_every_finding_in_round_one(self) -> None:
        """The review brief says so."""
        each(
            "test_all_findings",
            ["test_a_review_of_a_stage_lists_every_finding_in_the_first_round"],
        )

    def test_a17_a_merge_of_main_is_reviewed_for_the_merge_alone(self) -> None:
        """The merge-only review brief asks for nothing outside its scope."""
        each(
            "test_brief",
            [
                "test_a_merge_only_head_is_checked_for_the_merge_alone",
                "test_a_merge_only_review_asks_for_nothing_outside_its_scope",
            ],
        )

    def test_a24_an_escalation_carries_how_we_got_here(self) -> None:
        """A card without the section is refused."""
        each("test_how_we_got_here", ["test_a_card_without_it_is_refused"])

    def test_a26_no_line_is_added_to_a_doc(self) -> None:
        """An added line of a markup file is refused."""
        each("test_markup_lines", ["test_an_added_line_is_refused"])

    def test_a27_a_doc_that_restates_code_is_cut(self) -> None:
        """A claim against a changed guide is refused."""
        each("test_markup_claim", ["test_each_case"])

    def test_a28_the_session_url_footer_is_not_in_a_body(self) -> None:
        """The footer forms are removed."""
        each("test_sessionurl", ["test_removed_forms"])

    def test_a29_a_relock_and_a_zip_only_head_need_no_review(self) -> None:
        """A pins-only relock and a derived-only head are not reviewed."""
        each("test_pins_only", ["test_ok_is_ready_to_merge_with_no_review_line"])
        each("test_derived_only", ["test_only_the_zip_is_approved_before_merges"])


class TestSlots(unittest.TestCase):
    """The rules about slots, workers and briefs (B)."""

    def test_b1_every_running_agent_holds_a_slot(self) -> None:
        """An agent the ledger does not hold still takes a slot."""
        each(
            "test_slot_held",
            ["test_one_agent_holds_every_empty_slot_until_it_is_recorded"],
        )

    def test_b7_one_ticket_has_one_pr(self) -> None:
        """Two PRs on one ticket are named."""
        each(
            "test_slots_rules",
            ["test_b23_two_prs_on_one_ticket_are_named_oldest_first"],
        )

    def test_b8_a_newer_ticket_is_folded_into_the_older(self) -> None:
        """The fold line is printed."""
        each("test_folds", ["test_line"])

    def test_b11_the_task_list_is_state(self) -> None:
        """Each open PR has a line with its CI and agent."""
        each(
            "test_task_list",
            ["test_each_open_pr_has_a_line_with_its_ci_and_agent"],
        )

    def test_b12_the_checklist_lists_every_running_agent(self) -> None:
        """The running line comes first."""
        each("test_task_list", ["test_in_flight_comes_first_and_is_not_next"])

    def test_b13_a_lapsed_check_in_is_flagged(self) -> None:
        """The sweep fails an overdue check-in."""
        each("test_check_in", ["test_sweep_overdue_fails"])

    def test_b14_nox_is_before_a_push_not_after_every_edit(self) -> None:
        """The worker brief says it is a maximum."""
        each(
            "test_brief_nox",
            ["test_the_sentence_says_before_each_push_and_never_after_every_edit"],
        )

    def test_b18_a_hand_back_is_logged_once(self) -> None:
        """The log appends only a change."""
        each("test_slotlog", ["test_changes_and_append"])

    def test_b19_a_draft_is_refused(self) -> None:
        """A brief that opens a draft is refused naming the setting."""
        each("test_no_drafts", ["test_draft_is_refused_naming_the_setting"])

    def test_b20_a_hold_covers_a_push(self) -> None:
        """A push is held for the quiet period."""
        each("test_quiet", ["test_exactly_the_quiet_period", "test_push_that_goes_out"])

    def test_b24_a_polling_agent_is_named(self) -> None:
        """Only a sleeping shell call waits."""
        each("test_polling", ["test_only_a_sleeping_shell_call_waits"])

    def test_b25_the_text_lint_status_is_read(self) -> None:
        """The lint decides a body's form."""
        each("test_textlint", ["test_in_form"])

    def test_b26_expand_blocks_follow_the_head(self) -> None:
        """Each stale block is named."""
        each("test_evidence_head", ["test_each_stale_block_is_named"])


class TestHousekeeping(unittest.TestCase):
    """The rules about disk, runners, CI and pins (C)."""

    def test_c1_the_disk_is_cleaned_harder_under_pressure(self) -> None:
        """The pressure pass names what it freed."""
        each(
            "test_clean_pressure",
            ["test_pressure_names_the_pass_it_started_and_what_it_freed"],
        )

    def test_c2_nothing_under_dev_is_removed(self) -> None:
        """A path under /dev is refused."""
        each("test_clean_units", ["test_a_path_under_dev_is_refused_naming_the_path"])

    def test_c3_a_merged_worktree_goes_on_merge(self) -> None:
        """The marker of a merged worktree does not keep it."""
        each(
            "test_worktrees",
            ["test_the_marker_of_a_merged_worktree_does_not_keep_it"],
        )

    def test_c4_a_flake_is_not_rerun(self) -> None:
        """A flake re-run is refused; a GitHub problem's is not."""
        each(
            "test_rerun_rule",
            [
                "test_c13_a_flake_rerun_is_refused",
                "test_c13_a_run_stuck_queued_with_no_jobs_may_be_rerun",
            ],
        )

    def test_c5_a_failed_check_is_read_through_the_api(self) -> None:
        """The failed line comes from the status."""
        each("test_supersede", ["test_a_failed_line_when_the_status_failed"])

    def test_c6_a_flake_is_not_closed_until_addressed(self) -> None:
        """Next says a test is not quarantined."""
        each("test_flake", ["test_next_says_a_test_is_not_quarantined"])

    def test_c7_a_green_relock_ranks_last(self) -> None:
        """A relock review is last and a pins-only relock needs none."""
        each("test_slots_rules", ["test_b9_a_relock_review_is_last"])

    def test_c9_the_sweep_lists_every_org_repository(self) -> None:
        """Archived and excluded ones only are left out."""
        each(
            "test_owner_repositories",
            ["test_archived_and_excluded_repositories_are_left_out"],
        )

    def test_c10_the_sweep_runs_from_the_newest_pitboss(self) -> None:
        """An older version than the newest is said."""
        each("test_outdated", ["test_older_than_pypi"])

    def test_c11_what_the_orchestrator_creates_is_synced(self) -> None:
        """A changed file is committed and pushed."""
        each(
            "test_sync",
            ["test_a_changed_file_is_committed_and_pushed_to_main"],
        )

    def test_c12_a_stale_scratch_pr_is_closed(self) -> None:
        """Finished pulls are closed and their branches deleted."""
        each(
            "test_scratch",
            ["test_finished_pulls_are_closed_and_their_branches_deleted"],
        )
