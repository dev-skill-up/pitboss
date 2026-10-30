# Reading a sweep

`pitboss sweep` prints, in order: one line per open PR of the project and its
libraries, each followed by its action lines (in this order: `STALL`, `UPDATE`, `RULING DUE` or `PAUSE`, `WAIT-FOR-CI`, `CONFLICT`, one `FAILED` for each failed check, then `READY TO MERGE`, `MERGE BY HAND` or `AUTO MERGE OFF`); the runner-pressure line; the
merge-queue runs; the stragglers; the stale worktrees; the reminders; the
slot ledger. It exits 1 when any PR has a failed check or a merge conflict,
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
- `failed=[name (job id), ...]`: checks whose latest run on the head failed. An aggregate
  check failing usually means one of the jobs it gathers failed.
- `queue=`: the state of the PR's newest merge-queue run (`queued`,
  `in_progress`, or its conclusion), `-` when it has none.
- `review=`: `approved-this-head`; `approved-before-merges` (an older head
  was approved and only merges of the base came since; never in a gated
  repository); `changes-needed` (on this head); `older-head` (the review is
  of an older head: a fix came since and needs a review); `none`.

## Markers

Each line below starts with the marker, then the PR, run or path it is about.

| Marker | Meaning | What to do |
| :--- | :--- | :--- |
| `UNREADABLE` | The session cannot read a repository the configuration names; it is left out of this sweep. | Give the session access, or take the repository out of the configuration. |
| `STALL` | A relock PR (head branch starting `relock/`) whose required `check` run has been red for more than four hours (14400 seconds from the run's `completed_at`; exactly four hours is not yet one). The line says how long it has been red and, for each failing job, the names of its failed steps. A non-relock PR and a green relock PR print none. | A fix, taken before every other pull request but the merge of a ready one (`rules.md`, "A free slot is filled the same turn"): root-cause the failing steps now, since the next relock fails on the same errors until the fix lands. The `FAILED` line of the same PR says more of each failed check. A stalled PR that also has `RULING DUE` or `PAUSE` waits for the ruling or the owner first. |
| `UPDATE` | The PR is `behind` the base and every check of its head has finished (a behind PR whose checks still run prints none, and neither does a repository under `[merge_queue] repositories`, whose queue builds each entry on the current base). | Merge the base branch into the PR's branch (never rebase or force-push), check, push. It is kind `update` in the `NEXT` list of `slots next`, unless a review asks for changes on its head (then `fix the review`), or the PR has `RULING DUE` or `PAUSE` (then it is not listed). |
| `RULING DUE` | The review rounds of the PR hit the changes-needed limit and no ruling is recorded: the newest review asks for changes, and either the plan was graded changes needed in two reviews with no review grading it approved, or a review asks for changes once the plan has been graded approved (by that review or an earlier one) (`rules.md`, "Plan first, and two rounds of changes needed"). A review is read by its `Plan:` line (`Plan: approved` or `Plan: changes needed`; no `Plan:` line says nothing of the plan) and its verdict, newest last; only comments by trusted authors count. A ruling is recorded by a PR comment whose first line is exactly `Opus ruling`. | Start an Opus agent whose only brief is to make a ruling, and record it as that comment; its ruling is taken as given. The PR is not listed in `NEXT` for a fix, an update or a review round until then. |
| `PAUSE` | A review asks for changes (the newest review does) after a recorded ruling. | Opus never gets another shot: label the PR and its ticket `paused-owner`, comment what the rounds disagreed about and the options, stop listing both, and report the number and the options to the owner (`rules.md`, "Plan first, and two rounds of changes needed"). The PR is not listed in `NEXT` for a fix, an update or a review round. |
| `WAIT-FOR-CI` | No check run of the PR's head has completed (a draft that runs no CI, or checks not yet started or still running). It is never reviewed, approved or merged on this head, except the first review of a draft at its Plan stage, which its author's hand-back starts (`rules.md`, "Plan first"). | Wait for CI; a reviewer started on it, other than that first draft review, reports NOT STARTED. |
| `CONFLICT` | The PR has a merge conflict. | Merge the base branch into the PR's branch (never rebase or force-push someone's branch) and regenerate generated files with the project's own tooling. |
| `FAILED` | The latest run of a check on the head failed (a cancelled, skipped or superseded run is not one); the line says what api.github.com gives of it: the failed step names, the check output and its annotations (job logs are not downloaded, as the sandbox blocks them). | Find the root cause from that, and from the code it names. A flake is a bug, not a reason. Re-run failed jobs at most once, and only after the whole run finished. |
| `AUTO MERGE OFF` | A PR with nothing failing, no conflict and no changes-needed review has auto-merge off and is not in the queue. | Arm auto-merge again (a push clears it). |
| `READY TO MERGE` | Green, `clean`, and its review approves this head; auto-merge is off. | Arm auto-merge, or merge. |
| `MERGE BY HAND` | The same, in a repository without auto-merge. | Merge it now, by hand: no event will arrive to say it is ready. |
| `RUNNER PRESSURE` | A merge-queue run in a repository that shares the runners has a job waiting for a runner, or the quiet period is not over (the line says the minutes remaining). | Hold (below). |
| `NO RUNNER PRESSURE` | Nothing waits for a runner and the quiet period of `rules.md` is over (the sweep reads the record and writes nothing). | Push and merge as usual. |
| `QUEUE RUN` | An unfinished merge-queue run, with its age against the queue's time limit. | Nothing, unless it nears the limit while runners are short: then hold. |
| `STALE QUEUE RUN` | An unfinished run of a merge group that is no longer its PR's newest (GitHub rebuilds the groups behind a removed entry and leaves the old runs waiting). | `pitboss cancel-stale-runs <config>`, read the dry run, then again with `--no-dry-run`. If the cancel is refused, list the run ids for the owner. Never cancel a PR's newest group. |
| `CANCELLED STALE QUEUE RUN` | A stale run was cancelled (or, with "dry run", would be). | Nothing. |
| `COULD NOT CANCEL STALE QUEUE RUN` | GitHub refused the cancel. | It may have finished meanwhile; sweep again, and if it is still there, tell the owner. |
| `STRAGGLER` | A checkout on this machine with uncommitted files or commits on no remote branch. | Triage it (below). |
| `STALE WORKTREE` | A worktree whose work is finished and on GitHub. | `pitboss clean-worktrees <config>`, read the dry run, then `--no-dry-run`. |
| `REMOVED WORKTREE` | A stale worktree was removed (or, with "dry run", would be); its branch is kept. | Nothing. |
| `COULD NOT REMOVE WORKTREE` | git refused (a locked worktree, for one). | Look at it: someone may still be using it. |
| `SWEEP REMINDER` | A question each sweep ends with (the project's configuration may set its own). | Answer it before ending the sweep (below). |
| `EMPTY SLOT` | A worker slot has no agent. | See `slots.md`. |
| `SLOTS FREE` | `SLOTS FREE n`: fewer workers run than the slots configured (n of them free) and the queue has work. | Start work with `slots next`, and before the turn ends set a wake-up (`send_later`): nothing else wakes an idle orchestrator until a GitHub event. |
| `GONE AGENT` | The ledger holds an agent the session no longer runs. | See `slots.md`. |
| `CHECK BEFORE YOU ANSWER` | The ledger is kept by hand. | See `slots.md`. |
| `NEXT` | A line of the sorted list of what to start, printed by `pitboss slots next` (a sweep prints none). | See `slots.md`. |
| `NO HAND-BACK` | The ledger holds an agent started more than 10 minutes ago that has produced no hand-back or notification; the line gives its minutes. | See `slots.md`. |

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
itself:

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

A worktree is stale only when all hold: it is not the main clone and lies
under the workspace; nothing in it is uncommitted; every commit is on a
remote branch; nothing in it changed in the configured idle hours (by file
times, because a new worktree's tip is an old commit); and its branch's PR
merged or was closed, or, with no PR, its tip is in the base branch. A
worktree with an open PR is never stale. An agent that finishes removes its
own worktree; `clean-worktrees` is the net under that. Do not clean while an
agent is being started.

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
