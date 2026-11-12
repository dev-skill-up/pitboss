"""The sentences of the briefs (keyword: brief, pitboss#118).

Each is a template: ``{name}`` stands for a field of the PR or ticket, filled by
``brief.build``. The text is pinned by tests, so a change to it is a reviewed
code change.
"""

from . import causetext

WORKTREE = (
    "Worktree: work in your own `git worktree add` of {repo} {checkout}; never in"
    " the main clone. A task that changes a repository other than the ticket's"
    " gets a `git worktree add` of that repository, the only place to commit, and"
    " a shared clone (`main_clone`, the repository-prototype clone) is never"
    " checked out to another branch."
)
DRAFT = (
    "Draft: open the PR as a draft whose body has a Plan section (what you will"
    " change, and why that satisfies each Done-when line) and an Execution section"
    " (what you did, with the evidence for what CI does not show); never mark it"
    " ready."
)
READY = (
    "Ready: this project's PRs are not drafts; open the PR ready for review, its"
    " body with a Plan section and an Execution section."
)
BODY = (
    "PR body: its first line is `Fixes {ticket}`; it has a Plan, an Execution, a"
    " `Head: <40 hex>` line, and an Evidence section built by `uvx pitboss expand"
    ' TEMPLATE` from a template of plain `$ <command>` rows (the head is "$ git'
    ' rev-parse HEAD"), never retyped; check it with `uvx pitboss lint pr-body'
    " BODYFILE --config {config} --head <the head>`, which must print ok; after"
    " every PATCH of the body, fetch the stored body back (parsed with python3"
    " json) and lint that file the same way. A row the Plan points to CI has no"
    " row in the body."
)
EDIT = (
    "Edit: change files with the Edit tool only (no sed, no shell redirection, no"
    " ad hoc rm); clean up with `uvx pitboss clean-container {config}` only;"
    " change an existing comment or PR body only after reading its current text in"
    " full, and send the complete replacement, never a placeholder."
)
DENIED = (
    "Denied: when the classifier denies a command, look in the repository's"
    " Claude Code settings file's allow list for an equivalent allowed form and"
    " run that exact string; ask the owner to widen the list only when no entry"
    " fits."
)
LOCAL = (
    "Local checks: wrap each in `timeout 598`; a 124 is left to CI, never rerun"
    " with a longer limit. Never leave a command running, and never remove files"
    " under /dev (redirecting to /dev/null is fine)."
)
HOLD_BUG = (
    "A hold that comes from a known pitboss bug with a ticket is not waited out:"
    " push the branch with plain `git push origin <branch>` and cite the ticket in"
    " the hand-back (with no ticket yet, file one first); every other hold is"
    " kept (pitboss#218)."
)
PUSH_HELD = (
    "Push: push with `uvx pitboss push {config} --no-dry-run` (add `--draft` for a"
    " draft PR), after every commit. Under a hold it exits 1 and pushes nothing:"
    " hand back at once, naming where you stopped and the SHA of what is"
    " unpushed; never loop or sleep for the hold to clear. " + HOLD_BUG
)
PUSH_FREE = "Push: push the branch with `git push` after every commit."
PLAN_COMMANDS_WORKER = (
    "Plan commands: run each precise command of the Plan as written; if the"
    " Plan's command cannot show its row, change the Plan first and ask for its"
    " review."
)
TRY_COMMANDS = (
    "Try commands: run each command read-only before you write it into the Plan, when"
    " it can be run, and see that it shows its row (a test command needs the"
    " build it depends on; a filter must keep what the row needs, line numbers"
    " included); for a command that cannot be run (it needs the change, CI, a"
    " service or a long build), say so in the Plan."
)
NO_APPEND = (
    "Expand rows: never append anything to a row of the template (no `; echo"
    " $?`, no `|| echo`): `pitboss expand` prints `exit status: N` for a status"
    " that is not zero, and a row not run as the Plan wrote it is rejected."
)
SEARCH = (
    "Search: update the docstring next to each piece of code the change alters,"
    " and cut other text that no longer matches it; a change never adds a line"
    " to a doc, so a doc is cut, not reworded (pitboss#396)."
)
NO_WAITING = "No waiting: never wait for CI. Push, then hand back at once."
FINISH = "Finish inside the turn. Do not merge. Do not write the review."
HAND_BACK = (
    "Hand-back: the PR number, the exact head SHA, and what you ran locally (each"
    " command with the raw output `pitboss expand` printed) and, where the checks"
    " are nox sessions, the `pitboss nox` result of the pushed head (the four"
    " sessions and their status), and the `Deviations:` line (only a departure"
    " from the Plan's commands or the ticket's Done-when, or `none`); nothing"
    " else. Before you hand back, save it to a file and run `uvx pitboss"
    " hand-back-check FILE` (keyword: hand-back-done); hand back only on its `ok`."
)
NEW_PR_CHECKOUT = "from origin/{base} after `git fetch origin {base}`"
PR_CHECKOUT = "on the PR's branch, current with origin/{base}"

TASK_NEW_PR = (
    "Task: do the whole of ticket {reference} in one PR: write the code, then open"
    " the PR."
)
TASK_FIRST_ROUND = (
    "Task: PR {reference} has no Plan and Execution body. Fix as best you can and"
    " write the Plan and Execution in the body."
)
TASK_REVISE_PLAN = (
    "Task: PR {reference}: {review} did not approve the Plan. Edit the `## Plan`"
    " section of the PR body and change only what the"
    " findings name; touch no code, doc or test (a merge of {base} for a conflict"
    " excepted) and fix none of the Execution defects; push nothing, leave the"
    " `Head:` line as it is, and hand back the body digest (`pitboss"
    " body-digest`): the head has not moved, so the sweep offers the review of"
    " the Plan again (`older-body`) and the next round is the next round of the"
    " Plan stage (keyword: plan-revision, pitboss#221)."
)
TASK_FIX_REVIEW = (
    "Task: PR {reference}: fix the findings of {review}, each one, and nothing"
    " else: make no change that no finding names. The Plan is approved: do not"
    " change it."
)
TASK_FIX_CI = (
    "Task: PR {reference}: CI on the head {head} is red. Fix CI (a red CI is never"
    " a rejection); change only what makes it red. Read the log of each failed"
    " check first: " + causetext.RULE + ".{logs}"
)

TASK_RULING_STEPS = (
    "Task: PR {reference}: its newest `Opus ruling` comment rules `do these steps`."
    " Do exactly the steps of that ruling, in order, and nothing else; the ruling"
    " is taken as given."
)
TASK_RULING_AS_GIVEN = (
    "Task: PR {reference}: its newest `Opus ruling` comment rules to split, reshape"
    " or abandon. Do exactly what that ruling says to the ticket and the PR; it is"
    " not checked against the one-ticket-one-PR rules."
)
REVIEW = (
    "Review: {reference} at head {head}. Read the head from the PR when you start"
    " and again before you post; if it moved, review the new head."
)
SEPARATE = (
    "Separate agent: you are not the author; if you wrote any part of the change,"
    " say so and stop. You run nothing: you read the diff and the CI of the head."
)
CI = (
    "CI: first read the checks of the head SHA above; if one has not finished or"
    " has not passed, hand back `NOT STARTED: <check> is <state> at <sha>` and"
    " review nothing. Read the complete run of this head. A draft, or a head with"
    " an unfinished check, is `NOT STARTED`, not a verdict (pitboss#202)."
)
SEPARATE_DRAFT = (
    "Separate agent: you are not the author; if you wrote any part of the change,"
    " say so and stop. You run nothing: you read the diff and the PR body."
)
SEPARATE_DRY = (
    "Separate agent: you are not the author; if you wrote any part of the change,"
    " say so and stop. You run nothing but the dry runs of the Plan's commands:"
    " you read the diff and the CI of the head."
)
SEPARATE_DRAFT_DRY = (
    "Separate agent: you are not the author; if you wrote any part of the change,"
    " say so and stop. You run nothing but the dry runs of the Plan's commands:"
    " you read the diff and the PR body."
)
CI_DRAFT = (
    "Draft: this PR is a draft, and a draft runs no CI job (its check is reported"
    " skipped, never missing; keyword: draft-ci, pitboss#321), so there is no CI"
    " to read and none to wait for. You read the diff and the PR body only (and"
    " dry-run the Plan's commands); never hand back"
    " `NOT STARTED` for a missing check run of a draft."
)
FORM = (
    "Form: read `references/adversarial-review.md` of the sweep skill, then post"
    " one comment on the PR in the form of the repository, from `uvx pitboss"
    " review-form {config} {repo}`:"
)
GATED = (
    "Gated: this repository's review-gate.yml reads the comment, and the merge"
    " waits for it: {note}. A comment that breaks any of it leaves the status"
    " `adversarial-review` pending."
)
PLAN_DIGEST = (
    "Plan digest: you grade the Plan, so add {plan_digest_line} to the comment,"
    " beside the `Plan:` line, as given (it is what `uvx pitboss plan-digest`"
    " prints for the body this brief read). The sweep prints `PLAN EDITED` when"
    " the Plan section of the body later differs from it, and offers the PR for"
    " no round until an Opus ruling allows the edit."
)
NO_PLAN_EDIT = (
    "Approved Plan: do not edit the Plan section of an approved PR; hand back a"
    " Plan problem as NOT PROCEEDING with the evidence."
)
NO_PLAN_FINDING = (
    "Approved Plan: it is never reopened. A finding that asks for an edit of the"
    " Plan (a row, a test or a command added to it) is no finding of the"
    " Execution: do not post it as one and never ground changes needed on it;"
    " write it as a note for an Opus ruling, and judge the Execution against the"
    " Plan as written."
)
BODY_DIGEST = (
    "Body: the PR body is part of what you read. This brief read it as it stood"
    " when the sweep printed it (keyword: review-brief, pitboss#338): add the"
    " line `Body: {body_digest}` to the comment, beside the `Verdict:` line, as"
    " given. The sweep shows `review=older-body` for a body edited after the"
    " review of an unmoved head, and a review that records the new digest"
    " answers it. This brief is complete: the orchestrator dispatches it"
    " unchanged, and you copy its form, head and digest lines as given."
)
HONEST = (
    "Changes needed: a verdict of changes needed names, for each change, a failure"
    " a worker could hit by mistake (a forgotten step, an accidental"
    " paste). A finding that needs deliberate evasion (obfuscation, a script that"
    " fakes output) is a note: it is never a ground for changes needed, and it"
    " never starts a ruling."
)
NO_ATTACKS = (
    "Ask for no attack, bypass or adversarial input that the goal above does not"
    " name."
)
GOAL_ONLY = (
    "Judge the change against the goal above and the ticket's Done-when. " + NO_ATTACKS
)
GUARDS = (
    "Guards: a guard or lint exists to stop workers forgetting or retyping by"
    " inference. If this PR adds one, check that mistakes (an accidental"
    " paste included) are caught; do not hunt for deliberate obfuscation or for"
    " scripts that fake output. Gaps of that kind are not findings and get no"
    " ticket."
)
NO_EXIT = (
    "No exit clauses: if the Done-when is met as written the verdict approves; if"
    " a part is not met the finding is `do the done-when as written`, and nothing"
    " offers to ship less."
)
REVIEW_END = (
    "Do not push, merge, or edit the PR or its branch. Hand back after posting,"
    " with the comment's URL and nothing else."
)
CHECK = (
    "Check: the last `Head:` line of the PR body is the full SHA of the head; the"
    " Evidence is real output (a command and what it printed) run on that head,"
    " and every `$ ` block in it is one `pitboss expand` marked (a row the Plan"
    " points to CI has the pointer instead); every required"
    " check finished and passed at that head."
)
GREP = (
    "Grep: look for a docstring that contradicts the code it sits next to; one is"
    " changes needed, said as what the text now says instead. Other text that no"
    " longer matches the code is cut by the author, and a mention of it that was"
    " missed is no finding."
)
PLAN_COMMANDS_PLAN = (
    "Plan commands: for each Done-when row, if the Plan's evidence mentions a"
    " command, the Plan must give the precise command (the exact string to run on"
    " the head, a cut or a pipe included when the Plan wants one); a row that"
    " mentions a command without it is a changes-needed finding of the Plan."
    " Evidence that is not a command (a file read, a diff) is accepted when the"
    " Plan says exactly what will be shown; a CI run is accepted only as a CI"
    " pointer (the CI pointer rule)."
)
CARRIED = (
    "Write `Plan: approved (fixed)`, and an `Execution:` line with your"
    " verdict, the same word as the `Verdict:` line."
)
EXCLUSIVE = (
    " Where `references/adversarial-review.md` asks for more than this scope, this"
    " scope decides."
)

SCOPE_FULL = (
    "Scope: the full review of head {head}: the Plan and the Execution, against"
    " the goal and the ticket's Done-when. Grade both in one review, with a"
    " `Plan:` line and an `Execution:` line beside the one `Verdict:` line."
)
SCOPE_EXECUTION = (
    "Scope: the Execution of head {head}, against the approved Plan and the"
    " ticket's Done-when. The Plan is approved: grade only the Execution, and"
    " write `Plan: approved (fixed)` and an `Execution:` line with your verdict, the"
    " same word as the `Verdict:` line (a review with no `Execution:` line is not"
    " read: REVIEW UNREAD); do not reassess or discuss the Plan. A gap"
    " you see in the Plan is a request for an Opus ruling, never a Plan finding."
)
SCOPE_PLAN = (
    "Scope (exclusive): the Plan of head {head}, alone, against the goal and the"
    " ticket's Done-when. Write a `Plan:` line and the one `Verdict:` line (the"
    " Plan's verdict), no `Execution:` line and no defect of the Execution. Of the"
    " PR's facts only the last `Head:` line of the body is checked: it is the full"
    " SHA of the head."
)
SCOPE_RESOLUTION = (
    "Scope (exclusive): this head {head} differs from the approved head {approved}"
    " only by a merge of {base}. Check the merge commit's resolution against both"
    " parents, any file regenerated from the merge (a rebuilt zip), and the CI on"
    " the head, and nothing else: not the PR body (its Head line, footer or commit"
    " count included), not the approved change. A finding outside this scope is"
    " not a ground for changes needed; do not write it." + EXCLUSIVE
)
SCOPE_FIX_ROUND = (
    "Scope (exclusive): the fix round. The findings to check are those of"
    " {review}, of head {approved}. The diff to read is `git diff"
    " {approved}..{head}`. Check that each finding is fixed at head {head} as the"
    " finding asks, whether the fixes invalidate the approved Plan, and the CI on"
    " the head, and nothing else. You may raise nothing outside that diff or those"
    " findings: a finding outside this scope is not a ground for changes needed;"
    " do not write it. If every finding is fixed as asked and the fixes do not"
    " invalidate the approved Plan, the verdict is approved, and the PR is"
    " mergeable." + EXCLUSIVE
)
# keyword: all-findings (pitboss#169): a first round lists every finding, a later
# round checks those; a fix round is scoped to its diff and its findings
ALL_FINDINGS = (
    "Round: in the first round of a stage,"
    " read the whole PR body, the whole diff and every command of the Plan"
    " against the repository, and list every finding of the stage you grade in"
    " that one review, not the first few. A later round on the same stage (an"
    " earlier review of this PR graded it) checks only the earlier findings and"
    " the findings caused by the changes made since the head that review read."
)
MISSED_EARLIER = (
    "Missed earlier: a review that is not the first round and raises a finding"
    " that is present in the unchanged text of an earlier head says so, with one"
    " line for each such finding that starts with `Missed earlier:` and says what"
    " the finding is; the sweep counts those lines for the analysis of the rounds"
    " after an Opus ruling. A finding caused by the changes since has no such"
    " line."
)
PLAN_DRY_RUN = (
    "Dry run: in a review of the Plan, try each command of the Plan as a"
    " read-only dry run where it can be tried (it changes nothing in the"
    " repository, the PR or the machine), and report each that cannot run as"
    " written as a finding of the Plan."
)
PLAN_CHECK = (
    "Plan check: before you approve a Plan, the PR needs a"
    " comment whose first line is `Plan check` and whose last line is `Plan check:"
    " ok`, the output of `uvx pitboss plan-check <body file>` for this Plan (its"
    " `Plan digest:` line is the one you record); without it, or with a row that"
    " it says was NOT RUN (a command that cannot start, that waits on a lock or a"
    " queue, or that exceeds `timeout 598`), the Plan is changes needed and you do"
    " not approve it (keyword: plan-check, pitboss#192)."
)

SCOPE_RELOCK = (
    "Scope (exclusive): the relock {reference} at head {head}, which fixes no"
    " ticket and has no Plan or Execution of its own. The goal above is its"
    " goal: moves of pins are safe when the lock matches and CI is green. It"
    " changes nothing but pins (the compiler, the package repository, the"
    " locked package versions, the workflow pins); it is not judged against a"
    " Done-when, and its body needs no Plan, Execution or Evidence." + EXCLUSIVE
)
RELOCK_CHECKS = (
    "Relock checks: (1) the diff of the head touches only pins and locks"
    " (`bats.lock`, `.github/bats-version`, `.github/repository-version` and the"
    " workflow pins the relock names): a source, test or doc change is changes"
    " needed; (2) every pin moves forward to a version that exists, and the PR"
    " body lists the old and new versions it moves; (3) the lock matches"
    " `bats.toml` and the committed pins (the build fetches exactly the locked"
    " versions); (4) every required check finished and passed at that head; (5)"
    " the last `Head:` line of the body, when it has one, is the full SHA of the"
    " head. Run the project's pins-check command (`[relock] pins_check_command`) on"
    " the head and paste its output as your evidence: this relock is reviewed only"
    ' because the command did not print `OK` (`rules.md`, "A pins-only pull'
    ' request is verified by the pins-check command").'
)

RULING_WHO = (
    "Ruling: you are an Opus agent whose only brief is to make a ruling on PR"
    " {reference}. Read the PR, its ticket, its reviews and its comments. Write no"
    " code and no review."
)
RULING_RECORD = (
    "Record: write the ruling to a file and run `uvx pitboss ruling post"
    " OWNER/NAME#NUMBER FILE` (it posts the file as a comment on the PR and"
    " prints the comment's URL; never `gh api`), a file"
    " whose first line is exactly `Opus ruling` and whose second line is exactly"
    " `Ruling: <word>`, where <word> is one of these words: {words}; then a"
    " section headed `How we got here` (the analysis of"
    " this brief's `How we got here` line, checked against the PR); then"
    " the steps or the reasons. A step that edits the ticket or the PR body is one"
    " line `N. ticket delete: TEXT`, `N. body delete: TEXT` or `N. ticket replace:"
    " OLD => NEW` (or `body replace:`), and before you post, run `uvx pitboss lint"
    " ruling RULING TICKET BODY --head SHA` on the ruling, the ticket's body and the"
    " PR's body (`ruling post` runs it too and refuses a ruling whose steps fail"
    " plan-check or lint pr-body, naming the gate and the step). The ruling is"
    " taken as given."
)
RULING_HOW = (
    "How we got here: <the orchestrator writes this before the brief is sent: for"
    " each rejection before this ruling, the finding, the rule or brief line that"
    " should have prevented it, and the prevention filed (a pitboss ticket"
    " number)>. Refuse to rule without it: if this line is still the template,"
    " is empty, or names no prevention filed for a rejection, hand back NOT STARTED"
    " with what is missing, post no comment, and write no ruling."
)
RULING_END = "Hand back the comment's URL and nothing else."
