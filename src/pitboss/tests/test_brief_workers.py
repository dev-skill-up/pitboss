"""The briefs of a worker and of an Opus agent: the text is pinned (pitboss#118)."""

import dataclasses
import unittest

from .. import brief, briefconfig
from . import briefmake
from .briefmake import HEAD, HONEST, PROJECT, has_all, has_none, pinned, text

NEW_PR_PROCESS = [
    "Task: do the whole of ticket o/r#7 in one PR: write the code, then open the PR.",
    "Worktree: work in your own `git worktree add` of o/r from origin/main after"
    " `git fetch origin main`; never in the main clone.",
    "Done-when: read the ticket o/r#7 and all its comments first (they add"
    " requirements).",
    "Draft: open the PR as a draft whose body has a Plan section",
]
NEW_PR_BODY = [
    "PR body: its first line is `Fixes o/r#7`;",
    "built by `uvx pitboss expand TEMPLATE` from a template of plain"
    " `$ <command>` rows",
    "`uvx pitboss lint pr-body BODYFILE --config proj --head <the head>`, which"
    " must print ok. It ends with only this line: THE FOOTER",
]
NEW_PR_RULES = [
    "Edit: change files with the Edit tool only (no sed, no shell redirection, no"
    " ad hoc rm)",
    "Push: push with `uvx pitboss push proj --no-dry-run` (add `--draft` for a"
    " draft PR), after every commit.",
    "No waiting: never wait for CI. Push, then hand back at once.",
    "Finish inside the turn. Do not merge. Do not write the review.",
    "Hand-back: the PR number, the exact head SHA, and what you ran locally",
    "wrap each in `timeout 598`",
]
FIRST_ROUND = [
    "Task: PR o/r#3 has no Plan and Execution body. Fix as best you can and write"
    " the Plan and Execution in the body.",
    "PR body: its first line is `Fixes o/r#7`;",
    "on the PR's branch, current with origin/main;",
]
REVISE_PLAN = [
    "Task: PR o/r#3: the review at https://example.org/c/1 did not approve the"
    " Plan. Edit the `## Plan` section of the PR body (and its `Head:` line) and"
    " change only what the findings name; touch no code, doc or test (a merge of"
    " main for a conflict excepted) and fix none of the Execution defects; end"
    " with an empty commit (`git commit --allow-empty`) pushed to the branch, and"
    " patch the `Head:` line to it.",
]
FIX_REVIEW = [
    "Task: PR o/r#3: fix the findings of the review at https://example.org/c/1,"
    " each one, and nothing else: make no change that no finding names. The Plan"
    " is approved: do not change it.",
]
FIX_CI = [
    f"Task: PR o/r#3: CI on the head {HEAD} is red. Fix CI (a red CI is never a"
    " rejection); change only what makes it red."
]
CONFLICT = [
    "Task: PR o/r#3 conflicts with main. Merge main into its branch (never"
    " rebase, never force-push), resolve the conflict, rebuild every generated"
    " file that derives from the merge (a lock, a zip, a regenerated tree), and"
    " change nothing else."
]
RULING = [
    "Ruling: you are an Opus agent whose only brief is to make a ruling on PR"
    " o/r#3.",
    "whose first line is exactly `Opus ruling` and whose second line is"
    " `Ruling: ` and one of these words: `do these steps`, `revise the plan`,"
    " `execution is approved`, `split`, `reshape`, `abandon`, `escalate to the"
    " owner`;",
    HONEST,
    "Hand back the comment's URL and nothing else.",
]
PLAIN = briefconfig.Brief(
    drafts=False, holds=False, worker_lines=("Compiler: /x",), review_lines=()
)


class TestWorkerBriefs(unittest.TestCase):
    """The briefs of a worker's round."""

    def test_a_new_pr_brief_names_its_task_and_worktree(self) -> None:
        """The task, the worktree, the Done-when and the draft."""
        pinned(brief.Kind.NEW_PR, NEW_PR_PROCESS, reference="o/r#7")

    def test_a_new_pr_brief_carries_the_body_form(self) -> None:
        """The first line, expand, lint and the footer."""
        pinned(brief.Kind.NEW_PR, NEW_PR_BODY)

    def test_a_new_pr_brief_carries_the_repositorys_rules(self) -> None:
        """Edit, push, no waiting, hand-back."""
        pinned(brief.Kind.NEW_PR, NEW_PR_RULES)

    def test_a_project_without_drafts_or_holds_says_so(self) -> None:
        """The differences between projects are the configuration's."""
        found = text(brief.Kind.NEW_PR, project=PLAIN, footer="", ticket="")
        has_all(
            found,
            [
                "Ready: this project's PRs are not drafts; open the PR ready for"
                " review",
                "Push: push the branch with `git push` after every commit.",
                "`Fixes <ticket>`",
            ],
        )
        has_none(found, ["It ends with only this line", "pitboss push"])
        briefmake.last_line(found, "Compiler: /x")

    def test_a_footer_with_braces_is_printed_as_it_is(self) -> None:
        """The footer is a value, never a template."""
        pinned(
            brief.Kind.NEW_PR,
            ["It ends with only this line: {x} {0}"],
            footer="{x} {0}",
        )

    def test_the_first_round_writes_the_body(self) -> None:
        """The PR exists; its body is what is written."""
        pinned(brief.Kind.FIRST_ROUND, FIRST_ROUND)
        has_none(text(brief.Kind.FIRST_ROUND), ["Draft:"])

    def test_a_plan_revision_changes_only_what_the_findings_name(self) -> None:
        """The Plan section and the Head line, then an empty commit."""
        pinned(brief.Kind.REVISE_PLAN, REVISE_PLAN)
        has_none(text(brief.Kind.REVISE_PLAN), ["PR body: its first line"])

    def test_a_fix_round_carries_the_findings_and_nothing_else(self) -> None:
        """No change that no finding names; the Plan is not touched."""
        pinned(brief.Kind.FIX_REVIEW, FIX_REVIEW)

    def test_a_fix_round_without_an_address_names_the_newest_review(self) -> None:
        """A GitHub review has no address."""
        pinned(
            brief.Kind.FIX_REVIEW,
            ["fix the findings of the newest review, each one"],
            findings="",
        )

    def test_a_red_ci_is_no_rejection(self) -> None:
        """The head is named; only what makes it red changes."""
        pinned(brief.Kind.FIX_CI, FIX_CI)

    def test_a_conflict_is_merged_never_rebased(self) -> None:
        """Merge the base, never rebase or force-push, rebuild generated files."""
        pinned(brief.Kind.RESOLVE_CONFLICT, CONFLICT)

    def test_the_projects_worker_lines_end_the_brief(self) -> None:
        """A fact only the project knows is added after the process."""
        project = dataclasses.replace(PROJECT, worker_lines=("Gated: strict.",))
        found = text(brief.Kind.FIX_CI, project=project)
        briefmake.last_line(found, "Gated: strict.")


class TestRulingBrief(unittest.TestCase):
    """The brief of an Opus agent."""

    def test_the_ruling_is_recorded_in_the_form_the_flow_reads(self) -> None:
        """The first line, the second line and its words."""
        pinned(brief.Kind.RULING, RULING)
