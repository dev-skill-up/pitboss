"""The briefs of a worker and of an Opus agent: the text is pinned (pitboss#118)."""

import dataclasses
import unittest

from .. import brief, briefconfig
from . import briefmake
from .briefmake import HEAD, HONEST, PROJECT, pinned, text
from .says import has_all, has_none

NEW_PR_PROCESS = [
    "Task: do the whole of ticket o/r#7 in one PR: write the code, then open the PR.",
    "Worktree: work in your own git worktree of o/r, made with `git fetch origin"
    " main` then `git worktree add -b <branch> <dir> origin/main`; never in the"
    " main clone. A task that changes a repository other than the ticket's gets a"
    " worktree of that repository, the only place to commit, and a shared clone"
    " (`main_clone`, the repository-prototype clone) is never checked out to"
    " another branch.",
    "Done-when: read the Done-when in the body of the ticket o/r#7; only the body"
    " has it, and a comment adds nothing to it",
    "Draft: open the PR as a draft whose body has a Plan section",
]
NEW_PR_BODY = [
    "PR body: its first line is `Fixes o/r#7`;",
    "built by `uvx pitboss expand TEMPLATE` from a template of plain"
    " `$ <command>` rows",
    "`uvx pitboss lint pr-body BODYFILE --config proj --head <the head>`, which"
    " must print ok; after every PATCH of the body, fetch the stored body back"
    " (parsed with python3 json) and lint that file the same way."
    " A row the Plan points to CI has no row in the body.",
]
NEW_PR_RULES = [
    "Edit: clean up with `uvx pitboss clean-container proj` only; change an"
    " existing comment or PR body only after reading its current text in full",
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
    "with `git fetch origin fix-branch` then `git worktree add <dir> fix-branch`;"
    " if origin/main has moved, merge it into the branch (never rebase or"
    " force-push)",
]
REVISE_PLAN = [
    "Task: PR o/r#3: the review at https://example.org/c/1 did not approve the"
    " Plan. Edit the `## Plan` section of the PR body and change only what the"
    " findings name; touch no code, doc or test (a merge of main for a conflict"
    " excepted) and fix none of the Execution defects; push nothing, leave the"
    " `Head:` line as it is, and hand back the body digest (`pitboss"
    " body-digest`): the head has not moved, so the sweep offers the review of"
    " the Plan again (`older-body`) and the next round is the next round of the"
    " Plan stage (keyword: plan-revision, pitboss#221).",
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
    " rebase, never force-push), resolve the conflict (a line main deleted takes"
    " main's side, so the diff against main of every .md and .rst file adds no"
    " line), rebuild every generated file that derives from the merge (a lock, a"
    " zip, a regenerated tree), and change nothing else (but for the body, as"
    " `Conflict body:` says)."
]
RULING = [
    "Ruling: you are an Opus agent whose only brief is to make a ruling on PR"
    " o/r#3.",
    "whose first line is exactly `Opus ruling` and whose second line is"
    " exactly `Ruling: <word>`, where <word> is one of these words: `do these"
    " steps`, `revise the plan`, `execution is approved`, `split`, `reshape`,"
    " `abandon`, `escalate to the owner`;",
    HONEST,
    "Hand back the comment's URL and nothing else.",
]
RULING_STEPS = [
    "Task: PR o/r#3: its newest `Opus ruling` comment rules `do these steps`. Do"
    " exactly the steps of that ruling, in order, and nothing else; the ruling is"
    " taken as given.",
]
RULING_AS_GIVEN = [
    "Task: PR o/r#3: its newest `Opus ruling` comment rules to split, reshape or"
    " abandon. Do exactly what that ruling says to the ticket and the PR; it is"
    " not checked against the one-ticket-one-PR rules.",
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
        """The first line, expand and lint; no footer of the session's own."""
        pinned(brief.Kind.NEW_PR, NEW_PR_BODY)
        found = text(brief.Kind.NEW_PR)
        has_none(found, ["Generated with"])

    def test_a_new_pr_brief_carries_the_repositorys_rules(self) -> None:
        """Edit, push, no waiting, hand-back."""
        pinned(brief.Kind.NEW_PR, NEW_PR_RULES)

    def test_the_brief_bans_removing_under_dev_and_never_writing_to_it(self) -> None:
        """Only removing files under /dev is banned; a redirect to it is fine (#424)."""
        pinned(
            brief.Kind.NEW_PR,
            ["never remove files under /dev (redirecting to /dev/null is fine)."],
        )
        has_none(
            text(brief.Kind.NEW_PR), ["never write under /dev", "write under /dev"]
        )

    def test_a_project_without_drafts_or_holds_says_so(self) -> None:
        """The differences between projects are the configuration's."""
        found = text(brief.Kind.NEW_PR, project=PLAIN, ticket="")
        has_all(
            found,
            [
                "Ready: this project's PRs are not drafts; open the PR ready for"
                " review",
                "Push: push the branch with `git push` after every commit.",
                "`Fixes <ticket>`",
            ],
        )
        has_none(found, ["pitboss push"])
        briefmake.last_line(found, "Compiler: /x")

    def test_the_first_round_writes_the_body(self) -> None:
        """The PR exists; its body is what is written."""
        pinned(brief.Kind.FIRST_ROUND, FIRST_ROUND)
        has_none(text(brief.Kind.FIRST_ROUND), ["Draft:"])

    def test_a_plan_revision_changes_only_what_the_findings_name(self) -> None:
        """The Plan section only: nothing is pushed and the Head line stays."""
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

    def test_a_ruling_round_names_the_ruling_comment(self) -> None:
        """The steps of the ruling, or what it says to the ticket and the PR."""
        pinned(brief.Kind.RULING_STEPS, RULING_STEPS)
        pinned(brief.Kind.RULING_AS_GIVEN, RULING_AS_GIVEN)

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
