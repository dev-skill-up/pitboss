# Reading a sweep

`pitboss sweep` prints, in order: one line per open PR of the project and its
libraries, each followed by its action lines (in this order: `STALL`, `UPDATE`, `RULING DUE`, `RULING UNREADABLE`, `RULING ESCALATES` or `PAUSE`, `UNREADABLE REVIEW`, `GATE PENDING`, `WAIT-FOR-CI`, `CONFLICT`, one `FAILED` for each failed check, then `READY TO MERGE`, `MERGE BY HAND` or `AUTO MERGE OFF`); the runner-pressure line; the
merge-queue runs; the stragglers; the finished worktrees (removed or kept, or with `[clean] worktrees = "list"` listed as stale); the disk pressure; the
reminders; the slot ledger. It exits 1 when any PR has a failed check or a merge conflict,
so a loop can act on it.

## The PR line

```
owner/name#12 [clean] auto-merge=off pending=0 failed=[test (job 345)] queue=- review=none Title (branch)
```

- `[state]` is GitHub's `mergeable_state`: `clean` (mergeable, every
  requirement met), `behind` (the base moved on; in a repository with a merge queue it still queues, elsewhere see `UPDATE`), `blocked`
  (checks pending or red, or a required review missing), `dirty` (a merge
  conflict), `unstable` (non-required checks failing), `draft`, `has_hooks`,
  `unknown` (GitHub is still computing it: look again later).
- `auto-merge=on|off`: whether auto-merge is armed. A push clears it.
- `pending=N`: checks on the head that have not finished.
- `failed=[name (job id), ...]`: checks whose latest run on the head failed and that no newer passing commit status of the head answers (see `FAILED`). An aggregate
  check failing usually means one of the jobs it gathers failed.
- `queue=`: the state of the PR's newest merge-queue run (`queued`,
  `in_progress`, or its conclusion), `-` when it has none.
- `review=`: `approved-this-head`; `approved-before-merges` (an older head
  was approved and only merges of the base came since; never in a gated
  repository); `changes-needed` (on this head); `plan-changes-needed` (on this
  head, and the review graded the plan changes needed: the only round is a
  revision of the plan); `plan-approved` (on this head, a review that approved
  the plan alone: it is no approval to merge, the execution is reviewed next);
  `older-head` (the review is
  of an older head: a fix came since and needs a review); `older-body` (the
  review is of this head and records a `Body:` digest, and the PR body is not
  the one it recorded: the body was fixed after the review and the head did
  not move; `slots next` prints `NEXT ... (review the fix round's findings
  only)` for it, and a review of the same head that records the new digest
  makes the standing the review's own again; a review with no `Body:` line is
  keyed to the head alone); `none`.

## Markers

Each line below starts with the marker, then the PR, run or path it is about.

| Marker | Meaning | What to do |
| :--- | :--- | :--- |
| `OUTDATED` | The first line of a sweep, `OUTDATED pitboss <running> < <newest on PyPI>`, printed only when PyPI has a newer release than the one running (nothing when it is current, ahead, or PyPI cannot be read). The sweep that printed it was run by an older pitboss, and the bugs main has fixed since may be in what it printed. | Run the sweep again as `uvx pitboss sweep <config>` (the newest PyPI release; if the classifier denies that form, retry as the allow list's equivalent, `rules.md`, "A denied command is retried as the allow list's equivalent"), and act on that output, not this one. If the line comes back from `uvx` too, the cache is stale: `uvx --refresh pitboss sweep <config>`. |
| `UNREADABLE` | The session cannot read a repository the configuration names (it is left out of this sweep), or one API call for a single PR failed (`UNREADABLE owner/name#7: check-runs answered HTTP 500`; that PR has no other line, the exit is not affected; `jobs` names a merge-queue run left out of the runner count, and the pressure line holds, since a free runner cannot be told from a count that is incomplete; `UNREADABLE tickets` says no ticket is offered as new work while a PR is unread, since it may already work on one). | For a repository: give the session access, or take it out of the configuration. For a PR or queue run: sweep again; if it repeats, the call is named in the line. Start no new ticket meanwhile. |
| `UNREADABLE REVIEW` | `UNREADABLE REVIEW <repository>#<n>: <comment URL> is not in the review form: <what is wrong with its first line>`. A comment of a trusted author on the PR has a line starting `Verdict:`, `Plan:` or `Execution:`, but its first line is not the repository's review first line (the first line of the form `uvx pitboss review-form <config> <repository>` prints; for example `Independent review (a separate reviewer agent, not the author) of head <40 hex>: approved\|changes needed`). The sweep reads no review from it, so the PR line's `review=` (`none`, `plan-approved`, an older review's standing) does not describe it, and `RULING DUE` is not printed from it. | Ask the reviewer to post the review again in the form (first line exactly the repository's, then the `Plan:`, `Execution:` and `Verdict:` lines). Never judge a review the sweep cannot read: do not start a fix round, a ruling, an approval or a merge from its text, and do not read `review=` of that PR as the review's outcome until the sweep reads the new comment. |
| `GATE PENDING` | `GATE PENDING <repository>#<n>: adversarial-review <state>: <text> (<link>)`. The repository is gated (it has `.github/workflows/review-gate.yml`, or the configuration lists it under `[review] gated`) and the commit status `adversarial-review` of the PR's head is not `success` (or the head has none: `no status posted`). The repository will refuse the merge, whatever `review=` says: a review the sweep reads as `approved-this-head` is not one the gate reads until the status is success. While it is printed the PR gets no `READY TO MERGE`. | Read the gate's text in the line. `No adversarial review yet` or a text about the form: post a new comment in the form `uvx pitboss review-form <config> <repository>` prints (a comment is never edited: the gate ignores an edited review); `Adversarial review: changes needed`: it is a fix round; any other text: read the gate run at the link. Do not merge, and do not call the review approved, until a sweep prints no `GATE PENDING` for the PR. |
| `STALL` | A relock PR (head branch starting `relock/`) whose required `check` run has been red for more than four hours (14400 seconds from the run's `completed_at`; exactly four hours is not yet one). The line says how long it has been red and, for each failing job, the names of its failed steps. A non-relock PR and a green relock PR print none. | A fix, taken before every other pull request but the merge of a ready one (`rules.md`, "A free slot is filled the same turn"): root-cause the failing steps now, since the next relock fails on the same errors until the fix lands. The `FAILED` line of the same PR says more of each failed check. A stalled PR that also has `RULING DUE`, `RULING UNREADABLE`, `RULING ESCALATES` or `PAUSE` waits for the ruling or the owner first (the `paused-owner` label too). At any other stage `slots next` lists the PR as `resolve the conflict`, a draft or red-CI PR included, and a ruling's own work step comes after it. |
| `UPDATE` | The PR is `behind` the base and every check of its head has finished (a behind PR whose checks still run prints none, and neither does a repository under `[merge_queue] repositories`, whose queue builds each entry on the current base). | Merge the base branch into the PR's branch (never rebase or force-push), check, push. It is not a kind in the `NEXT` list of `slots next`: that list takes the PR's kind from the flow's step alone (`pitboss next` prints the same step), and the flow has no update step. |
| `RULING DUE` | The flow's step for the PR is `OPUS_RULING` (`pitboss.flow.next_step`; `pitboss next CONFIG TICKET` prints it): the plan was rejected a second time with no ruling recorded, or the execution was rejected a second time on the approved plan after a fix round (a push that is more than a merge of the base, or an edit of the PR body: the reviews record the body's `Body:` digest, so two rejections of one head with a body fix between them count; two with nothing changed between them are one round). A review that approves the plan and asks for execution changes is not one: it is a worker round (`fix the review`). A ruling is recorded by a PR comment whose first line is exactly `Opus ruling`. The rounds are stated once, in the function (`rules.md`, "Plan first, and two rounds of changes needed"). | Start an Opus agent whose only brief is to make a ruling, and record it as that comment; its ruling is taken as given. The PR is not listed in `NEXT` for a fix, an update or a review round until then, and its `STALL`, `UPDATE`, `CONFLICT` and `FAILED` lines wait for the ruling. |
| `PAUSE` | The flow's step for the PR is `PAUSE_FOR_OWNER` (`pitboss.flow.next_step`): a review asks for changes on the plan, or on the execution, and it was posted after a recorded ruling that can be read. A ruling that no review follows is never one (it is followed as `RULING ESCALATES` or by the work it names), and neither is a ruling that cannot be read (`RULING UNREADABLE`). | Opus never gets another shot: label the PR and its ticket `paused-owner`, comment what the rounds disagreed about and the options, stop listing both, and report the number and the options to the owner (`rules.md`, "Plan first, and two rounds of changes needed"). The PR is not listed in `NEXT` for a fix, an update or a review round, and its `STALL`, `UPDATE`, `CONFLICT` and `FAILED` lines wait for the owner. |
| `RULING UNREADABLE` | `RULING UNREADABLE <repository>#<n>: <comment URL> is not in the ruling form: the second line must be 'Ruling: <word>', <word> one of: do these steps, revise the plan, execution is approved, split, reshape, abandon, escalate to the owner; ...`. The flow's step for the PR is `FIX_RULING` (`pitboss.flow.next_step`, checked right after the pause label, so a draft gets it too): the newest trusted comment whose first line is exactly `Opus ruling` has no second line `Ruling: <word>` with one of those words (a newer such comment hides an older readable ruling). The PR is not paused, and no review followed a ruling that could be read, so `PAUSE` is not printed from it. | An agent edits the comment, or posts the ruling again, with the second line exactly `Ruling: <word>`; never start another Opus agent (that is `RULING DUE`). The PR is not listed in `NEXT` for a fix, an update or a review round until the comment is in form, and its `STALL`, `UPDATE`, `CONFLICT` and `FAILED` lines wait. |
| `RULING ESCALATES` | The flow's step for the PR is `RULING_ESCALATES`: the newest ruling can be read and says `escalate to the owner`, and no review follows it. | The same as `PAUSE`: label the PR and its ticket `paused-owner`, comment the options, stop listing both, and report the number and the options to the owner. The PR is not listed in `NEXT` for a round, and its `STALL`, `UPDATE`, `CONFLICT` and `FAILED` lines wait for the owner. |
| `WAIT-FOR-CI` | No check run of the PR's head has completed (a draft that runs no CI, or checks not yet started or still running). It is never reviewed, approved or merged on this head, except a review of a draft at its Plan stage (its first review, or the review of a revised plan), which its author's hand-back starts (`rules.md`, "Plan first"). | Wait for CI; a reviewer started on it, other than such a draft review, reports NOT STARTED. A draft whose Plan is approved is undrafted when `can_undraft` holds (`pitboss pressure` passes), before any CI wait, so its checks run and it is offered for the review of its Execution (`rules.md`, "Plan first"); a draft whose Plan is not approved is never undrafted and has the `DRAFT ROUND` line instead of this one. |
| `DRAFT ROUND` | `DRAFT ROUND <repository>#<n>: <round>; a draft has no check run, ...` (keyword: draft-review, pitboss#156). A draft whose step is a round: `review it` (no review, or a review of an older head, of its Plan), `revise the plan` or `fix the review` (a review at its head asks for changes). It is the line `slots next` prints for the PR, in the same words, and it replaces `WAIT-FOR-CI` for it. | Take it as the `NEXT` line says: a draft is in progress, so it is worked before any `start a PR` line. A reviewer reads the diff and the PR body only: a draft has no check run, and a reviewer never hands back NOT STARTED for a missing one. |
| `PR STATE` | `PR STATE <repository>#<n>: [draft ]next step: <words>` (keyword: red-status, pitboss#162). `slots next` prints one for every open PR that was read, so none is absent: the words of its `NEXT` line when it is offered for a round, `waiting for CI at this head`, or the text of its step (paused, ruling, undraft, merge). | Read it when a PR has no `NEXT` line: it says what the PR waits for. |
| `BLOCKED` | `BLOCKED <repository>#<n>: status <context> <state> (<link>): <description>` (keyword: red-status, pitboss#162), in `slots next` and in the PR's lines of the sweep. A commit status of the head failed or errored, and no later passing check run of that name answers it. The line says `blocked by the open ticket <link> (named by ...)` for each open ticket that the status description, a label of the PR or a label of the ticket the PR fixes names (`#N`, `owner/repo#N` or an issue URL; a closed or unreadable ticket is left out), and, in `slots next`, the other open PRs on which the same status fails. For the `text-lint` context it adds the cause: `about the BODY of the PR (<first finding>)` when pitboss's lint of the body finds something, `about the PIN, not the body` when it finds nothing (the tool the workflow runs is at fault; a relock branch and a bot's PR are exempt from the lint, so theirs is always the pin). | Body: fix the body, and the lint runs again on the edit. Pin: fix the pin (the ticket that moves it), and edit no body. The PR is still listed in `NEXT` for its round. The other form is `BLOCKED <ticket> by <owner/repo#n>` (keyword: ticket-blocked, pitboss#163), in `slots next` and in the sweep: a ticket that is blocked in the form of `rules.md`, "A blocked ticket is not started" (keyword: ticket-blocked), while the ticket or PR it names is open. It has no `NEXT` line and no slot takes it. | Nothing for the blocked ticket: the next ticket takes the slot, and the blocker is worked first. When the blocker closes or merges the ticket is listed again in its place in the order. |
| `CONFLICT` | The PR has a merge conflict. | Merge the base branch into the PR's branch (never rebase or force-push someone's branch) and regenerate generated files with the project's own tooling. A PR with `RULING DUE`, `RULING UNREADABLE`, `RULING ESCALATES` or `PAUSE` waits for the ruling or the owner first (the `paused-owner` label too). At any other stage `slots next` lists the PR as `resolve the conflict`, a draft or red-CI PR included, and a ruling's own work step comes after it. |
| `FAILED` | The latest run of a check on the head failed (a cancelled, skipped or superseded run is not one), and the newest of the check run and the commit status of the head that answers it is the failure: a check run is answered by a passing status posted after it completed when the status's context is the check's name, or when the Actions run its `target_url` names is the check's run or a run of the same workflow file (a workflow's job `lint` that posts the context `text-lint`: the names differ, the workflow does not). A later passing status prints no `FAILED` line; a status older than the failure, or one that is not `success`, does not clear it. The line says what api.github.com gives of it: the failed step names, the check output and its annotations (job logs are not downloaded, as the sandbox blocks them). | Find the root cause from that, and from the code it names. A flake is a bug, not a reason. Re-run failed jobs at most once, and only after the whole run finished. A PR with `RULING DUE`, `RULING UNREADABLE`, `RULING ESCALATES` or `PAUSE` waits for the ruling or the owner first (the `paused-owner` label too). At any other stage `slots next` lists the PR as `resolve the conflict`, a draft or red-CI PR included, and a ruling's own work step comes after it. |
| `REMOVED FROM QUEUE` | `REMOVED FROM QUEUE <pr>: <time>, failed job of its last queue run: <job name>: <failed step>` (keyword: removed-from-queue). The PR's timeline has an `added_to_merge_queue` event and a later `removed_from_merge_queue` event as its newest queue event, it is not merged and auto-merge is off, in a repository under `[merge_queue] repositories`. The time is the removal's; the job and step are read from the jobs of the PR's newest merge group (`queue=` shows its run). With no failed job the line says `no failed job in its last queue run: cancelled by the queue`; with no run of the PR among the newest runs listed it says so, and the cause is unknown. A PR added again after the removal prints none. When the PR would get a `READY TO MERGE` or `AUTO MERGE OFF` line (nothing failing, no conflict, not a draft, and a review that approves this exact head, or the Opus ruling), the next line is `READY TO MERGE <pr>: arm auto-merge`, in place of those lines. With any other standing (a review of an older head, none, or one that asks for changes) the removal line is printed alone, with no merge action: arming auto-merge there could merge a head nobody approved. | Read the cause in the line before arming: a failed job is a `FAILED` to root-cause (a flake is a bug, and a dependency fetch failure is a ticket in the repository that owns the job), a cancelled group needs only the re-arm. Then arm auto-merge when the next line says so (never merge by hand around the queue); when it is the removal line alone, the head is reviewed first. |
| `AUTO MERGE OFF` | A PR with nothing failing and no conflict, whose newest review approved this exact head (`review=approved-this-head`), has auto-merge off and is not in the queue. With any other review (`none`, `older-head`, `older-body`, `approved-before-merges`, `changes-needed`, `plan-changes-needed`, `plan-approved`) no line is printed: arming auto-merge there could merge a head nobody approved (a head the Opus ruling approved gets `READY TO MERGE` while auto-merge is off). | Arm auto-merge again (a push clears it). |
| `READY TO MERGE` | Green, `clean`, and its review approves this head (or the newest Opus ruling can be read, says `execution is approved` and no review follows it, so the flow's step is MERGE); and, in a gated repository, the head's `adversarial-review` status is success (no `GATE PENDING`); auto-merge is off. | Arm auto-merge, or merge. |
| `MERGE BY HAND` | The same, in a repository without auto-merge (for a head the Opus ruling approved the line says `execution approved by the Opus ruling`). | Merge it now, by hand: no event will arrive to say it is ready. |
| `RUNNER PRESSURE` | A merge-queue run in a repository that shares the runners has a job waiting for a runner, or the quiet period is not over (the line says the minutes remaining). | Hold (below). |
| `NO RUNNER PRESSURE` | Nothing waits for a runner and the quiet period of `rules.md` is over (the sweep reads the record and writes nothing). | Push and merge as usual. |
| `QUEUE RUN` | An unfinished merge-queue run, with its age against the queue's time limit. | Nothing, unless it nears the limit while runners are short: then hold. |
| `STALE QUEUE RUN` | An unfinished run of a merge group that is no longer its PR's newest (GitHub rebuilds the groups behind a removed entry and leaves the old runs waiting). | `pitboss cancel-stale-runs <config>`, read the dry run, then again with `--no-dry-run`. If the cancel is refused, list the run ids for the owner. Never cancel a PR's newest group. |
| `CANCELLED STALE QUEUE RUN` | A stale run was cancelled (or, with "dry run", would be). | Nothing. |
| `COULD NOT CANCEL STALE QUEUE RUN` | GitHub refused the cancel. | It may have finished meanwhile; sweep again, and if it is still there, tell the owner. |
| `STRAGGLER` | A checkout on this machine with uncommitted files or commits on no remote branch. | Triage it (below). |
| `ORPHANED CHECKOUT` | A directory whose `.git` file points at a gitdir that is gone (a worktree whose main checkout was removed); git cannot read it, so it has no straggler line. | Look in the directory for files worth keeping, then delete it by hand; nothing in it is on a branch. |
| `STALE WORKTREE` | Printed only under `[clean] worktrees = "list"`: a worktree whose work is finished and on GitHub and that passes the safety test ("Stale worktrees", below). | `pitboss clean-worktrees <config>`, read the dry run, then `--no-dry-run`. |
| `REMOVED WORKTREE` | A finished worktree was removed (or, under `clean-worktrees` without `--no-dry-run`, would be); its branch is kept. A sweep prints it under `[clean] worktrees = "auto"` (the default), with the space freed on the last line of the section. | Nothing. |
| `KEPT WORKTREE` | A finished worktree that is not removed, with the reason: commits on no remote branch, changed tracked files, a `.pitboss-live` marker or live path, the directory the command runs in or one above it, a change within the idle hours, a link, a mount point, a checkout git cannot read, or untracked files (`git worktree remove` refuses them). | Triage it like a `STRAGGLER` when the reason is work that exists only here; otherwise nothing: it is removed by a later sweep once the reason is gone. |
| `COULD NOT REMOVE WORKTREE` | git refused (a locked worktree, for one). | Look at it: someone may still be using it. |
| `SCRATCH PR` | An open PR of a `[scratch]` repository that is not a kept fixture, in one of two forms (keyword: scratch). `SCRATCH PR owner/repo#N: run finished, close the PR and delete its branch`: every workflow run of its head has finished (a head with no run yet counts as finished once the PR is ten minutes old); printed only under `[clean] worktrees = "list"`, since the default closes it ("Scratch PRs", below). `SCRATCH PR owner/repo#N: head branch B is not one of ...; reuse one of them for the next run`: its head branch is not in `[scratch] branches`, whether its run has finished or not. A PR whose runs are still going and whose branch is a run branch prints no line, and a fixture named in `[scratch] keep` never does. | Close the PR and delete its branch, or run `pitboss clean <config>`; next time reuse a run branch. |
| `CLOSED SCRATCH PR` | A sweep (under `[clean] worktrees = "auto"`) or `pitboss clean` closed a scratch PR whose run finished. | Nothing. |
| `DELETED SCRATCH BRANCH` | The head branch of a scratch PR it closed was deleted. | Nothing. |
| `COULD NOT CLOSE SCRATCH PR` | GitHub refused to close a scratch PR; the line gives the HTTP status. | Close it by hand, or give the session the access; the next sweep tries again. |
| `COULD NOT DELETE SCRATCH BRANCH` | A branch of a closed scratch PR is still there, with the reason: another open PR has it as its head (a run branch is reused), its head is in another repository, or GitHub refused (a session may not be allowed to delete a branch). | Nothing for the first two. For a refusal, leave it: the run branches are reused, and the next run force-pushes into one ("Scratch PRs", below). |
| `clean:` | The first lines of a sweep (keyword: auto-clean): the mode (`disk under 90% used`, or `DISK OVER 90% (...)`: aggressive), what was removed and the space freed, what is never touched (a worktree with an open PR, a running worker's directory, the main clone, the directory the sweep runs in; under pressure each open-PR worktree is named), and a total. The sweep has removed it already. | Nothing. Never ask the owner about it ("Automatic cleaning", below). |
| `DISK PRESSURE` | A filesystem of the workspace or of a `[clean] scratch` directory has less free than `[clean] min_free_gib` (default 5 GiB; 0 never warns). The line says how much is free; indented lines under it name the largest safe dead paths (at most five), or say that none was found. A sweep scans for them only under pressure. | `pitboss clean-container <config>`, read the dry run, then `--no-dry-run` ("Disk", below). |
| `REMOVED PATH` | A dead path was removed by `clean-container` (or, with "dry run", would be): its size and why it is dead. | Nothing. |
| `KEPT PATH` | A dead path with work that exists only here (commits on no remote branch, in any branch or the stash of a standalone clone; changed tracked files), or that git cannot read, a bare repository, a mount point inside it or a path that cannot be looked at; never removed. | Triage it like a `STRAGGLER`. |
| `COULD NOT REMOVE PATH` | `rm` left the path in place, the path was looked at again just before its removal and was live, busy or unsafe, or a path of the `--approved` file is not a safe dead path directly in a configured root now. | Look at it: someone may still be using it. |
| `SWEEP REMINDER` | A question each sweep ends with (the project's configuration may set its own). | Answer it before ending the sweep (below). |
| `EMPTY SLOT` | A worker slot has no agent. | See `slots.md`. |
| `SLOTS FREE` | `SLOTS FREE n`: fewer workers run than the slots configured (n of them free) and the queue has work. | Start work with `slots next`, and before the turn ends set a wake-up (`send_later`): nothing else wakes an idle orchestrator until a GitHub event. |
| `GONE AGENT` | The ledger holds an agent the session no longer runs. | See `slots.md`. |
| `CHECK BEFORE YOU ANSWER` | The ledger is kept by hand. | See `slots.md`. |
| `NEXT` | A line of the sorted list of what to start, printed by `pitboss slots next` (a sweep prints none). | See `slots.md`. |
| `HOLD` | `HOLD new pull requests: <repository> (<n> open)`, once, while the owner's hold applies (`[holds] new_pull_requests`: more than `max_open` pull requests of a listed repository are open). | Start no new pull request in that repository: finish its open ones. `slots next` offers none of its tickets (`HELD`). |
| `HELD` | A line of `pitboss slots next`: a ticket of a held repository, `HELD (no new pull requests in <repository>: <n> open) <ticket>`. It has no `NEXT` number and no slot takes it. | Nothing: the next ticket takes the slot (`slots.md`). |
| `SUGGESTION` | One of the top five suggestions printed by `pitboss next CONFIG` and `pitboss slots next`: `SUGGESTION n of m: <kind>: <PR or ticket>: <model class>`, then the complete brief, then `--- end of suggestion n ---`; or `SUGGESTION: none` when nothing could start, or `SUGGESTION: n more queued, not shown`. The first is the one the process requires (a PR at `RULING DUE` first, with an Opus agent and no slot), the others are the next ones that could start. | Paste the brief of the first suggestion you can start, unchanged (`rules.md`, "Briefs come from pitboss"). If the first cannot start (the slot cap, a missing checkout), take the next one. |
| `NO HAND-BACK` | The ledger holds an agent started more than 10 minutes ago that has produced no hand-back or notification; the line gives its minutes. | See `slots.md`. |
| `SYNCED` | A sweep (or `pitboss sync`) copied a working file that changed to `notes-current` of the `[sync]` repository's main (`SYNCED <path>`). A sweep with nothing to commit (the files are identical to the remote, or a copy stages nothing) prints `sync: nothing to commit`, makes no commit and is not an error. | Nothing. |
| `SYNC NOT CONFIGURED` | The configuration has no `[sync]` table, so nothing the orchestrator creates is kept; the line is `SYNC NOT CONFIGURED: add a [sync] table (reference: sweep.md, "The orchestrator's working files")`, and the sweep exits 1. | Add a `[sync]` table to the configuration (below), run `uvx pitboss sync <config>`, and sweep again. |
| `NOT SYNCED` | A file beside the configuration (`*.toml`, `*.tsv`, `*.md`) or named by it (the slots file, the notes) is not in `[sync] paths`, and is not one of the files the sync keeps by itself (the configuration, the ledger, the log, the record); the line is `NOT SYNCED <path>`, one for each file, and the sweep exits 1. | Add the path to `[sync] paths` in the configuration, run `uvx pitboss sync <config>`, and sweep again; or move the file out of the configuration's directory if it is not the orchestrator's. |
| `SYNC SOURCE MISSING` | A file the sync is told to keep (the configuration or a `[sync] paths` entry) is not there. | Restore it from `notes-current` of the repository (below), or take it out of `[sync] paths`. |
| `NOT THE ORCHESTRATOR CONFIG` | The first line of a sweep of a configuration that does not own the slot ledger (`[slots] ledger-owner = true`, or the path the ledger records): the slots and `NEXT` lines of that sweep are not the orchestrator list, and `slots next`, `free` and `set` refuse that configuration. The line ends with `use <path>`. | Sweep again with the configuration it names, and refill slots only from that one (`slots.md`, "Which configuration refills the slot"). |
| `COULD NOT SYNC` | git could not bring the sync clone up to date or push to main; the line says why. Nothing was lost: the next sync sends the same files. | Fix what the line says (access, network) and run `uvx pitboss sync <config>`. |

## The orchestrator's working files (keyword: sync)

A container restart loses what is outside a repository: the sweep
configurations, the slot ledger and log, the pressure record, the notes and the
memory files. The `[sync]` table of the configuration (`repository`, default
`moshez/claude-jsonl`; `directory`, default `notes-current`; `paths`, the
files to keep) names them, and `pitboss sync <config>` copies the configuration,
the ledger, the log, the record and every `paths` entry into `directory`, each
under its own absolute path, commits and pushes straight to main. A sweep runs
it last, so a restart loses at most one sweep's changes.

- A file the orchestrator creates (a configuration, a note, a memory file) is
  added to `[sync] paths` in the same turn, and `uvx pitboss sync <config>` is
  run.
- At session start, a configuration or working file that is missing is
  restored from `notes-current` of that repository: the file at
  `notes-current/<absolute path>` is copied back to `/<absolute path>`.
  The `[sync]` table itself is in the configuration, so the configuration is
  the first file to restore.

## What the orchestrator reads of a PR

The orchestrator dispatches a new reviewer when the sweep shows a review is
due, and reads no PR body, diff or evidence first. The reviewer checks the Head
line, that the Evidence is real output on the head, and the checks (`rules.md`,
"Reviews"). The only reads the orchestrator makes of a PR are the sweep's
markers and the review's verdict line.

## The runner-pressure hold

Runners are shared between the merge queue and everything else. While a
queue run waits for a runner, every push, new PR, merge or re-run in any
repository that shares them adds runs ahead of it, and a queue run that
waits past its time limit is dequeued (`CI_TIMEOUT`).

While `RUNNER PRESSURE` is printed:

- do not push to a non-draft PR, mark a PR ready, enqueue or merge (by hand
  or by re-arming auto-merge), or re-run jobs, in any repository the
  configuration lists under runners; pushes to a draft PR, and opening one,
  start no costly job and are not held;
- tell every running agent to hold its pushes to non-draft PRs and keep working locally
  (design, proofs, local checks), committing locally only; unpushed work is
  expected during a hold;
- reading runs and logs, filing and commenting on issues, and reviews that
  start no runs are fine.

When `pitboss pressure <config>` exits 0 and reads `NO RUNNER PRESSURE` (the
quiet period of `rules.md` is over; `RUNNER PRESSURE` with minutes remaining
is still a hold), release held work one push at a time, running it
between pushes. Re-queue PRs that
were dequeued with `CI_TIMEOUT` first, since they were already paid for once;
then the rest in the order of `slots.md`. Say in your report whether the
sweep ran under pressure and what it held back. When the pressure comes
from this session's own PRs and runs, say so and reduce them.

## Leaving the merge queue

A PR leaves the queue with one of GitHub's reasons, and is not re-queued by
itself. The sweep prints `REMOVED FROM QUEUE` for it, with the time and the
failed job and step of its last queue run, so it is not noticed from the
timeline by hand; the reasons below say what to do about the cause:

- `CI_FAILURE`: a check failed on the merge group. Root-cause it as for
  `FAILED`; re-arm auto-merge once it is fixed.
- `MERGE_CONFLICT`: as for `CONFLICT`.
- `INVALID_MERGE_COMMIT`: the group could not be built; it has happened to a
  PR whose history held merge commits of another queued PR. Squashing the
  branch onto the base fixes it.
- `CI_TIMEOUT`: the group waited too long; usually runner pressure. Re-queue
  it first when the pressure clears.

## Stragglers

A straggler is finished or unfinished work that exists only on this machine,
which is reclaimed after a while. Each `STRAGGLER` line is triaged:

- an agent is working in it: leave it;
- its work merged under another SHA (squashed): remove the checkout;
- unpushed and unmerged: push it (when there is no runner pressure, or as a
  draft) so it
  becomes a PR, and say so; during a hold, write down on its issue where it
  is, so the next session finds it;
- scratch: read its `git status`, then delete it.

A straggler older than a day with `branch-on-origin=no` and commits not on
origin is the dangerous kind: deal with it before anything else (a `STALL` fix
included: unpushed work can be lost, and a fix waits).

## Stale worktrees

A worktree is finished when it is not the main clone, lies under the workspace,
and its branch's PR merged or was closed, or, with no PR, its tip is in the base
branch. A worktree on no branch, or on the base branch, is finished once its tip
is in the base branch (unlike a checkout of "Disk" below), so a persistent one
carries `.pitboss-live`. A worktree with an open PR is never finished. A finished worktree is
removed only when it passes the safety test, the one `clean-container` and the
`DISK PRESSURE` line use: every commit in it is on a remote branch, no tracked
file in it is changed (untracked files are scratch), nothing in it changed in the
configured idle hours (by file times, because a new worktree's tip is an old
commit), it holds no `.pitboss-live` marker and is not a live path, it is no
link or mount point, and it is not the directory the command runs in or a
directory above it. A finished worktree that passes but holds untracked files is
kept too, with their count, because `git worktree remove` refuses it. By default
(`[clean] worktrees = "auto"`) the sweep removes
every finished worktree that passes, printing `REMOVED WORKTREE`, and prints
`KEPT WORKTREE` with the reason for each that fails; the section ends with a
line giving the count removed, the space freed and the count kept. With
`"list"` the sweep removes nothing and prints `STALE WORKTREE` for each finished
worktree that passes; `clean-worktrees` then removes them. An agent that
finishes removes its own worktree; the sweep is the net under that. A worktree
an agent is starting in has files changed within the idle hours, so it is kept.

## Scratch PRs

A scratch repository (the `[scratch]` table, keyword: scratch) is a repository
whose only use is a run on a real GitHub that a feature branch cannot show (a
workflow that runs from the default branch, a fixture). Its table lists the
repositories (`repositories`), the fixture PRs that stay open (`keep`, as
`owner/name#N`, for example the fixture of a hold test) and the fixed branch
names a run reuses (`branches`, for example `scratch-run-1` and
`scratch-run-2`). The sweep reads every open PR of those repositories except the
kept fixtures, and reads the workflow runs of each head: when all have
finished the run is done and the PR is junk (`SCRATCH PR`, or `CLOSED SCRATCH
PR` and `DELETED SCRATCH BRANCH` under the default `"auto"`, which closes the PR
and deletes its branch, `pitboss clean` too; `clean --dry-run` and `"list"` only
list). A fixture is never closed, its branch never deleted. A branch another
open PR still has as its head, or one in a fork, is kept, with the reason. A PR
whose runs are still going prints no line. How a run uses the table is in
`rules.md`, "Scratch repositories".

## Automatic cleaning

A sweep starts by cleaning (`pitboss clean <config>` is the same on its own;
`--dry-run` removes nothing), with no prompt and no dry run: the finished
worktrees and dead checkouts, and the test tempdirs (`/tmp/tmp????????`, the
session user's, untouched for `[clean] tmp_hours`, default 24 hours). At 90% or
more of a file system used (`[clean] pressure_percent`) it is aggressive: tempdirs
untouched for an hour, every worktree and checkout with no open PR, and the
package caches that regenerate. A worktree with an open PR, a running worker's
directory (changed within the idle hours, or marked `.pitboss-live`), the main
clone and the sweep's own directory are never touched, and a worktree with
commits on no remote branch or a changed tracked file is kept (`KEPT WORKTREE`).
The agent never asks the owner whether to clean, and when the classifier denies
an `rm` it runs `uvx pitboss clean <config>` (which the allow list covers) and
does not stop.

## Disk

`pitboss clean-container <config>` lists the dead paths of the machine and
`--no-dry-run` removes them. A path is dead when it is one of:

- a git checkout directly under the workspace whose PR merged or closed, or
  whose tip is in the base branch with no PR (a checkout on the base branch or
  on no branch is never dead: it is a persistent checkout; a sweep under `auto`
  has already removed the finished worktrees of the main clone, judged as in
  "Stale worktrees" above, where a worktree on no branch or on the base branch
  can be finished);
- an entry of a `[clean] scratch` directory (not a symbolic link) with nothing
  in it changed in the idle hours (`[worktrees] idle_hours`);
- a regular file directly in `--root` (default `/`) written over `--hours`
  (default 1) after `--marker` (default `/container_info.json`, skipped when
  absent), which is judged like the others and is in the disk pressure scan.

It is never listed when it is marked live: a file named `.pitboss-live` is in
it at any depth or in a directory above it, it is, holds or lies in a path of
`[clean] live`, it is the main clone, it is or holds the directory the command
runs in, or its tree changed in the idle hours (a running agent's checkout;
`.git` contents do not count). The tool walks a path
once, never follows a symbolic link (a link is neither judged by what it
points at nor sized through) and never enters a mount point. A dead path is
safe when every git checkout in it, at any depth, has all its commits on a
remote branch and no changed tracked file; untracked files are scratch. A
standalone clone counts every ref (other local branches and the stash); a
worktree of another repository counts its HEAD. The others, and a path with a
checkout git cannot read, a bare repository or a mount point in it, are
`KEPT PATH` lines and are never removed. The dry run prints each safe path as `REMOVED PATH ... (dry run)`,
largest first, with its size and reason, and a last line with the total.

To approve a subset, write its paths one to a line in a file and pass
`--approved FILE`: only those paths are removed, and a path of the file that is
not among the safe dead paths now, or not directly in the workspace, a scratch
directory or `--root`, is `COULD NOT REMOVE PATH`. Removal runs
`rm -rf --one-file-system` on at most `--batch` paths at a time (default 5), so a
sandbox that refuses one large delete still completes; each part is looked at
again just before its `rm`, and a path that is live, busy or unsafe by then is
left in place;
the last lines give the space freed and the free space before and after.
`clean-container` fetches each repository first and does not judge the
checkouts of one that cannot be fetched (it says so).

## The reminders

The two default questions:

- Is any ticket closeable? For a ticket whose work merged, read the merged
  PR against the ticket's done-when, comment the evidence, and close it. A
  ticket with an item left open stays open and names the ticket that carries
  the item.
- Is any blocked ticket unblocked? A ticket that waits on something: check
  it; when it is done, say so on the ticket, and the ticket is workable in
  its turn.

Then compare the sweep with the session's task list and update what moved.
