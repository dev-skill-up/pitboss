"""The briefs of a review: the text is pinned here (pitboss#118)."""

import dataclasses
import unittest

from hamcrest import assert_that, equal_to

from .. import brief
from . import briefmake
from .briefmake import APPROVED, GOAL, HEAD, HONEST, has_none, pinned, text

RESOLUTION_SCOPE = (
    f"Scope (exclusive): this head {HEAD} differs from the approved head"
    f" {APPROVED} only by a merge of main. Check the merge commit's resolution"
    " against both parents, any file regenerated from the merge (a rebuilt zip),"
    " and the CI on the head, and nothing else: not the PR body (its Head line,"
    " footer or commit count included), not the approved change. A finding"
    " outside this scope is not a ground for changes needed; do not write it."
    " Where `references/adversarial-review.md` asks for more than this scope,"
    " this scope decides."
)
RESOLUTION = "\n".join(
    [
        f"Goal: {GOAL}",
        f"Review: o/r#3 at head {HEAD}. Read the head from the PR when you start"
        " and again before you post; if it moved, review the new head.",
        RESOLUTION_SCOPE,
        "Write `Plan: approved` as carried over, and an `Execution:` line with"
        " your verdict, the same word as the `Verdict:` line.",
        "Separate agent: you are not the author; if you wrote any part of the"
        " change, say so and stop. You run nothing: you read the diff and the CI"
        " of the head.",
        "CI: first read the checks of the head SHA above; if one has not finished"
        " or has not passed, hand back `NOT STARTED: <check> is <state> at <sha>`"
        " and review nothing (a draft at its Plan stage has no check run).",
        "Form: read `references/adversarial-review.md` of the sweep skill, then"
        " post one comment on the PR in the form of the repository, from `uvx"
        " pitboss review-form proj o/r`:",
        "    ## Review",
        f"    Reviewed: {HEAD}",
        "    Verdict: <approved or changes needed>",
        HONEST,
        "Ask for no attack, bypass or adversarial input that the goal above does"
        " not name.",
        "Do not push, merge, or edit the PR or its branch. Hand back after"
        " posting, with the comment's URL and nothing else.",
    ]
)
GUARDS = (
    "Guards: a guard or lint exists to stop workers forgetting or retyping by"
    " inference. If this PR adds one, check that honest mistakes (an accidental"
    " paste included) are caught; do not hunt for deliberate obfuscation or for"
    " scripts that fake output. Gaps of that kind are not findings and get no"
    " ticket."
)
OUTSIDE_THE_MERGE = [
    "Check: the last `Head:` line",
    "Evidence is real output",
    "Grep:",
    "Scope: the full review",
    "Judge the change against the goal",
    "No exit clauses",
    "Guards:",
]
FULL = [
    f"Scope: the full review of head {HEAD}: the Plan and the Execution,"
    " against the goal and the ticket's Done-when.",
    "Check: the last `Head:` line of the PR body is the full SHA of the head;",
    "Grep: look for a statement the change makes false",
    "No exit clauses: if the Done-when is met as written",
]
NO_ATTACKS = (
    "Ask for no attack, bypass or adversarial input that the goal above does not"
    " name."
)
FULL_SCOPES = (
    brief.Kind.REVIEW_FULL,
    brief.Kind.REVIEW_EXECUTION,
    brief.Kind.REVIEW_PLAN,
)
EXECUTION = [
    f"Scope: the Execution of head {HEAD}, against the approved Plan",
    "write `Plan: approved` as carried over; do not reassess or discuss the Plan.",
]
PLAN = [
    f"Scope (exclusive): the Plan of head {HEAD}, alone,",
    "no `Execution:` line and no defect of the Execution.",
    "Of the PR's facts only the last `Head:` line of the body is checked",
]
FORM_LINES = [
    "from `uvx pitboss review-form proj o/r`:\n    ## Review\n"
    f"    Reviewed: {HEAD}\n    Verdict: <approved or changes needed>\n",
    f"Review: o/r#3 at head {HEAD}.",
    "You run nothing",
    "Do not push, merge, or edit the PR or its branch.",
]
FIX_ROUND = [
    "Scope (exclusive): the fix round. The findings to check are those"
    " of the review at https://example.org/c/1, of head " + APPROVED,
    f"Check that each is fixed at head {HEAD} as the finding asks,"
    " and the CI on the head, and nothing else: not a part of the"
    " change that no finding names, not the Plan. A finding outside"
    " this scope is not a ground for changes needed; do not write it.",
]


class TestEveryBrief(unittest.TestCase):
    """What every brief starts with."""

    def test_each_brief_starts_with_the_original_goal(self) -> None:
        """The first line is the goal, taken from the ticket, in one line."""
        for kind in brief.Kind:
            assert_that(text(kind).splitlines()[0], equal_to(f"Goal: {GOAL}"))


class TestReviewScopes(unittest.TestCase):
    """The scope of a review is exactly one of 2a, 2b and 2c, and exclusive."""

    def test_a_merge_only_head_is_checked_for_the_merge_alone(self) -> None:
        """2a: the whole brief is pinned, word for word."""
        found = text(brief.Kind.REVIEW_RESOLUTION)
        assert_that(found, equal_to(RESOLUTION))

    def test_a_merge_only_review_asks_for_nothing_outside_its_scope(self) -> None:
        """No body check, no Head line, no Evidence, no Grep, no Done-when walk."""
        has_none(text(brief.Kind.REVIEW_RESOLUTION), OUTSIDE_THE_MERGE)

    def test_a_first_review_is_the_full_review_of_the_head(self) -> None:
        """2b: the Plan and the Execution of that head, with the body checks."""
        pinned(brief.Kind.REVIEW_FULL, FULL)
        has_none(text(brief.Kind.REVIEW_FULL), ["Scope (exclusive)"])

    def test_a_review_of_an_approved_plan_grades_the_execution_only(self) -> None:
        """The Plan line is carried over, not reassessed."""
        pinned(brief.Kind.REVIEW_EXECUTION, EXECUTION)

    def test_a_plan_review_grades_the_plan_alone(self) -> None:
        """No Execution line and no Execution defect; only the Head line."""
        pinned(brief.Kind.REVIEW_PLAN, PLAN)
        has_none(text(brief.Kind.REVIEW_PLAN), ["Check: the last `Head:` line"])

    def test_the_review_after_a_fix_round_checks_the_findings(self) -> None:
        """2c: the findings of the review it names, and nothing else."""
        pinned(brief.Kind.REVIEW_FIX_ROUND, FIX_ROUND)
        found = text(brief.Kind.REVIEW_FIX_ROUND)
        has_none(found, ["Grep:", "No exit clauses", "Judge the change against"])

    def test_a_fix_round_review_without_an_address_names_the_newest_review(
        self,
    ) -> None:
        """A GitHub review has no address."""
        pinned(
            brief.Kind.REVIEW_FIX_ROUND,
            ["those of the newest review, of head " + APPROVED],
            findings="",
        )


class TestReviewRules(unittest.TestCase):
    """What every review brief says."""

    def test_a_changes_needed_names_a_failure_an_honest_worker_could_hit(self) -> None:
        """A finding that needs deliberate evasion is a note, never a ruling."""
        for kind in brief.REVIEWS:
            pinned(kind, [HONEST, NO_ATTACKS])

    def test_a_guard_review_checks_honest_mistakes_only(self) -> None:
        """Obfuscation and faked output are not hunted and get no ticket."""
        for kind in FULL_SCOPES:
            pinned(kind, [GUARDS])

    def test_the_review_form_is_filled_in_and_the_head_named(self) -> None:
        """The comment's lines are the repository's, with the head."""
        pinned(brief.Kind.REVIEW_FULL, FORM_LINES)

    def test_the_projects_review_lines_end_the_brief(self) -> None:
        """A fact only the project knows is added, after the process."""
        project = dataclasses.replace(briefmake.PROJECT, review_lines=("Gated: x.",))
        found = text(brief.Kind.REVIEW_FULL, project=project)
        briefmake.last_line(found, "Gated: x.")
