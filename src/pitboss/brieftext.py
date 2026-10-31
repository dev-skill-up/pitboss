"""The sentences of the briefs (keyword: brief, pitboss#118).

Each is a template: ``{name}`` stands for a field of the PR or ticket, filled by
``brief.build``. The text is pinned by tests, so a change to it is a reviewed
code change.
"""

ONE_PR = (
    "One PR: first confirm that the ticket can be satisfied by one PR. If it can,"
    " do the whole ticket in one PR. If it cannot, hand back NOT STARTED with the"
    " evidence (what you searched, what you tried, why one PR is impossible) and"
    " split nothing yourself."
)
WORKTREE = (
    "Worktree: work in your own `git worktree add` of {repo} {checkout}; never in"
    " the main clone."
)
DONE_WHEN = (
    "Done-when: read the ticket {read} and all its comments first (they add"
    " requirements). Its Done-when, as written, is the standard: you copy it word"
    " for word into the Plan, and nobody narrows it or offers an alternative to"
    " it."
)
DRAFT = (
    "Draft: open the PR as a draft whose body has a Plan section (what you will"
    " change, and why that satisfies each Done-when line) and an Execution section"
    " (what you did, with the evidence); never mark it ready."
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
    " BODYFILE --config {config} --head <the head>`, which must print ok."
    "{footer_note}"
)
FOOTER_NOTE = " It ends with only this line: {footer}"
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
    " with a longer limit. Never leave a command running, and never write under"
    " /dev."
)
PUSH_HELD = (
    "Push: push with `uvx pitboss push {config} --no-dry-run` (add `--draft` for a"
    " draft PR), after every commit. Under a hold it exits 1 and pushes nothing:"
    " hand back at once, naming where you stopped and the SHA of what is"
    " unpushed; never loop or sleep for the hold to clear."
)
PUSH_FREE = "Push: push the branch with `git push` after every commit."
NO_WAITING = "No waiting: never wait for CI. Push, then hand back at once."
FINISH = "Finish inside the turn. Do not merge. Do not write the review."
HAND_BACK = (
    "Hand-back: the PR number, the exact head SHA, and what you ran locally (each"
    " command with the raw output `pitboss expand` printed); nothing else."
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
    " section of the PR body (and its `Head:` line) and change only what the"
    " findings name; touch no code, doc or test (a merge of {base} for a conflict"
    " excepted) and fix none of the Execution defects; end with an empty commit"
    " (`git commit --allow-empty`) pushed to the branch, and patch the `Head:`"
    " line to it."
)
TASK_FIX_REVIEW = (
    "Task: PR {reference}: fix the findings of {review}, each one, and nothing"
    " else: make no change that no finding names. The Plan is approved: do not"
    " change it."
)
TASK_FIX_CI = (
    "Task: PR {reference}: CI on the head {head} is red. Fix CI (a red CI is never"
    " a rejection); change only what makes it red."
)
TASK_RESOLVE_CONFLICT = (
    "Task: PR {reference} conflicts with {base}. Merge {base} into its branch"
    " (never rebase, never force-push), resolve the conflict, rebuild every"
    " generated file that derives from the merge (a lock, a zip, a regenerated"
    " tree), and change nothing else."
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
    " review nothing (a draft at its Plan stage has no check run)."
)
FORM = (
    "Form: read `references/adversarial-review.md` of the sweep skill, then post"
    " one comment on the PR in the form of the repository, from `uvx pitboss"
    " review-form {config} {repo}`:"
)
HONEST = (
    "Changes needed: a verdict of changes needed names, for each change, a failure"
    " an honest worker could hit (a mistake, a forgotten step, an accidental"
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
    " inference. If this PR adds one, check that honest mistakes (an accidental"
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
    " and every `$ ` block in it is one `pitboss expand` marked; every required"
    " check finished and passed at that head (a draft has no check run: say that"
    " none was read)."
)
GREP = (
    "Grep: look for a statement the change makes false or contradictory anywhere"
    " in the tree; one is changes needed. An objection to a phrase no claim"
    " depends on is answered by removing the phrase."
)
CARRIED = (
    "Write `Plan: approved` as carried over, and an `Execution:` line with your"
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
    " write `Plan: approved` as carried over; do not reassess or discuss the"
    " Plan."
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
    " {review}, of head {approved}. Check that each is fixed at head {head} as the"
    " finding asks, and the CI on the head, and nothing else: not a part of the"
    " change that no finding names, not the Plan. A finding outside this scope is"
    " not a ground for changes needed; do not write it." + EXCLUSIVE
)

RULING_WHO = (
    "Ruling: you are an Opus agent whose only brief is to make a ruling on PR"
    " {reference}. Read the PR, its ticket, its reviews and its comments. Write no"
    " code and no review."
)
RULING_RECORD = (
    "Record: post a comment on the PR whose first line is exactly `Opus ruling`"
    " and whose second line is `Ruling: ` and one of these words: {words}; then"
    " the steps or the reasons. The ruling is taken as given."
)
RULING_END = "Hand back the comment's URL and nothing else."
