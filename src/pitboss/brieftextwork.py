"""The sentences of a worker brief about how to wait on the checks (pitboss#175).

Like those of ``brieftext``, they are pinned by tests, so a change to them is a
reviewed code change.
"""

from typing import Mapping

from . import briefkind, brieftext as text, brieftextbody, brieftextfix, brieftextowner
from .envrules import LIMIT

NOX = (
    "Nox: where the checks are nox sessions, run `timeout "
    + LIMIT
    + " pitboss nox` before"
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
    " under `timeout " + LIMIT + "`, or one `Monitor` with an `until` loop."
)
FIRST_DESIGN = (
    "First design: throwing away a first design is acceptable and is not a thing"
    " to avoid; rewrite it when the tests show it is wrong."
)
TASK_RUN_PLAN = (
    "Task: PR {reference}: its Plan was approved alone (a review with a `Plan:` line"
    " and no `Execution:` line), after an Opus ruling, so its commands were never"
    " run. Run each precise command of the Plan as written, and fill the Execution"
    " and Evidence of the PR body with what they printed. The Plan is approved: do"
    " not change it (pitboss#201)."
)
TASK_ADD_CI_QUOTES = (
    "Task: PR {reference} is ready and its checks passed, and its Plan has CI-quote"
    " rows the body does not answer yet. Add each quote to the Execution as a line"
    " that starts `CI quote:` and points to the run (the workflow, the job URL of"
    " the head, the step and a greppable string that step prints), as the CI"
    " pointer rule says; paste no log output. Change nothing else; the Plan is"
    " approved (pitboss#277)."
)
TASK_REFRESH_BODY = (
    "Task: PR {reference}: its body names an older head than the PR's (the last"
    " `Head:` line, or an Evidence block expanded at another commit), so `text-lint`"
    " is red. Run `uvx pitboss body-head {reference}` (it adds the `Head:` line for"
    " the head and changes nothing else) and `uvx pitboss expand` again for each"
    " stale Evidence block, then `uvx pitboss lint pr-body BODYFILE` on the body as"
    " `gh api` prints it, which must print ok. Change no code (keyword: stale-head,"
    " quire#1115)."
)
TASK_SHARED_RED = (
    "Task: PR {reference}: its failed check is red on other PRs of the repository"
    " (or on main) with the same first error line, so the cause is shared (read"
    " its failure, and the same check of the repository's other open PRs and main)."
    " Fix no PR: search the open tickets for the check name, and file ONE ticket"
    " against the shared cause (a stale pin, a stale lock or a runner outage is"
    " the cause, not any PR), or add the PRs to the ticket that exists, then stop."
    " Each PR goes back to its own step when the shared red is closed (keyword:"
    " shared-red)."
)
DEVIATIONS = (
    "Deviations: the hand-back, and the PR body, have a `Deviations:` line naming"
    " only a departure from the Plan's commands or the ticket's Done-when"
    " (`pitboss nox` run more than once on one head is one; `--all` is not"
    " feedback); how a file is edited (a heredoc, the Edit tool, `sed`), a"
    " virtualenv, a redirected output file or a research fetch is never a"
    " deviation, and the line is `Deviations: none` beside them; it is part of"
    " the form of the hand-back, and a hand-back without it is NOT STARTED and"
    " is sent back."
)
TEMP_RUNS = (
    "Temp files: a check that runs more than once gets its own `TMPDIR`, removed"
    " right after each run; a run that needs more than 1 GiB is left to CI."
)
DEPENDENCY = (
    "Dependency: a ticket that depends on another open ticket is not impossible in"
    " one PR and is never ground for a split: if you hand back"
    " NOT STARTED for it, name the ticket it waits for; the orchestrator does that"
    " ticket first, and adds a repository the mission needs (add_repo) without"
    " asking."
)
DRAFT_STATE = (
    "Draft state: never change a PR's draft state, in either direction (the"
    " sweep marks a PR ready); if your push shows a state you did not expect, say"
    " so in your hand-back."
)
SENTENCES = (
    NOX,
    NOX_ORDER,
    FIRST_DESIGN,
    DEVIATIONS,
    TEMP_RUNS,
    DEPENDENCY,
    DRAFT_STATE,
    brieftextowner.OWNER,
    *brieftextbody.SENTENCES,
)
TASK_FIX_BLOCKED_BY = (
    "Task: PR {reference}: its `Blocked-by:` lines name a loop (each PR waits for"
    " the next) or a blocker that closed without merging or cannot be read."
    " Correct the lines of the"
    " body: drop the one that is wrong, or name the PR or ticket that now carries"
    " the change, then `uvx pitboss lint pr-body BODYFILE` on the body as `gh api`"
    " prints it must print ok. Change no code (keyword: blocked-by)."
)
TASK_AFTER_BLOCKER = (
    "Task: PR {reference}: the PRs it was blocked by have merged since its red check"
    " finished. Merge the base into the branch, check,"
    " push (never rewrite history), then `uvx pitboss body-head {reference}`: CI"
    " runs again on the new head (keyword: blocked-by)."
)
TASK_FINISH_PARTIAL = (
    "Task: PR {reference}: a worker handed it back unfinished and nothing offered it"
    " again (its decision names what is missing). Resume"
    " this PR on its own branch, never a new one: do what the line says (post the"
    " `uvx pitboss plan-check`, fix the body until `uvx pitboss lint pr-body BODYFILE`"
    " prints ok, push the unpushed commits), change nothing else, then stop with the"
    " hand-back (keyword: finish-partial)."
)

Kind = briefkind.Kind
TASKS: Mapping[Kind, str] = {
    Kind.NEW_PR: text.TASK_NEW_PR,
    Kind.FIRST_ROUND: text.TASK_FIRST_ROUND,
    Kind.REVISE_PLAN: text.TASK_REVISE_PLAN,
    Kind.FIX_REVIEW: text.TASK_FIX_REVIEW,
    Kind.FIX_ROUND: brieftextfix.TASK_FIX_ROUND,
    Kind.FIX_CI: text.TASK_FIX_CI,
    Kind.RESOLVE_CONFLICT: brieftextfix.TASK_RESOLVE_CONFLICT,
    Kind.RULING_STEPS: text.TASK_RULING_STEPS,
    Kind.RULING_AS_GIVEN: text.TASK_RULING_AS_GIVEN,
    Kind.RUN_PLAN: TASK_RUN_PLAN,
    Kind.ADD_CI_QUOTES: TASK_ADD_CI_QUOTES,
    Kind.REFRESH_BODY: TASK_REFRESH_BODY,
    Kind.SHARED_RED: TASK_SHARED_RED,
    Kind.FIX_BLOCKED_BY: TASK_FIX_BLOCKED_BY,
    Kind.AFTER_BLOCKER: TASK_AFTER_BLOCKER,
    Kind.FINISH_PARTIAL: TASK_FINISH_PARTIAL,
}
