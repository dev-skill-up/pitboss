# Reading a sweep

`pitboss sweep` prints, in order: one line per open PR of the project and its
libraries, each followed by its action lines (in this order: `STALL`, `UPDATE`, `FIXED ON BASE`, `RULING DUE`, `RULING UNREADABLE`, `RULING ESCALATES`, `PAUSE` or `PLAN EDITED`, `PLAN ROW`, `UNREADABLE REVIEW`, `REVIEW NOTE`, `RULING NO ANALYSIS`, `GATE PENDING`, `WAIT-FOR-CI`, `CONFLICT`, one `FAILED` for each failed check, then `PINS-ONLY OK` or `PINS-ONLY`, then `READY TO MERGE`, `MERGE BY HAND` or `AUTO MERGE OFF`); the runner-pressure line; the
merge-queue runs; the stragglers; the finished worktrees (removed or kept, or with `[clean] worktrees = "list"` listed as stale); the disk pressure; the
reminders; the slot ledger; the `OPUS RULINGS DAILY` line when a day's summary is owed. It exits 1 when any PR has a failed check (not one that passed on the base since: `FIXED ON BASE`) or a merge conflict,
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
  revision of the plan, except that when an older review approved the Plan and
  recorded a `Plan digest:`, a Plan section revised after it is `PLAN EDITED`
  and the PR is offered no round until a ruling `revise the plan`); `plan-approved` (on this head, a review that approved
  the plan alone, or any review with a `Plan:` line that grades nothing and no graded `Execution:` line (the
  gradeline reads a grade word followed by `.`, `,`, `:` or `;` and words, so `Plan: approved. The audit row ...` grades;
  anything else after the word grades nothing): it is no approval to merge; after an Opus ruling the
  Plan's commands are run first (the worker round `run the Plan's commands and fill the Execution`));
  `older-head` (the review is
  of an older head: a fix came since and needs a review); `older-body` (the
  review is of this head and records a `Body:` digest, and the PR body is not
  the one it recorded: the body was fixed after the review and the head did
  not move (the `review the fix round's findings
  only` line is only for a review of changes needed of an older head); a review of the same head that records the new digest
  makes the standing the review's own again; a review with no `Body:` line is
  keyed to the head alone); `none`.

## Markers

Each line below starts with the marker, then the PR, run or path it is about.

| Marker | Meaning | What to do |
| :--- | :--- | :--- |
| `OUTDATED` | The first line of a sweep, `OUTDATED pitboss <running> < <newest on PyPI>`, printed only when PyPI has a newer release than the one running (nothing when it is current, ahead, or PyPI cannot be read). The sweep that printed it was run by an older pitboss, and the bugs main has fixed since may be in what it printed. | Run the sweep again as `uvx pitboss sweep <config>` (the newest PyPI release; if the classifier denies that form, retry as the allow list's equivalent, `rules.md`, "A denied command is retried as the allow list's equivalent"), and act on that output, not this one. If the line comes back from `uvx` too, the cache is stale: `uvx --refresh pitboss sweep <config>`. |
| `UNREADABLE` | The session cannot read a repository the configuration names (it is left out of this sweep), or one API call for a single PR failed (`UNREADABLE owner/name#7: check-runs answered HTTP 500`; that PR has no other line, the exit is not affected; `jobs` names a merge-queue run left out of the runner count, and the pressure line holds, since a free runner cannot be told from a count that is incomplete; `UNREADABLE tickets` says no ticket is offered as new work while a PR is unread, since it may already work on one). | For a repository: give the session access, or take it out of the configuration. For a PR or queue run: sweep again; if it repeats, the call is named in the line. Start no new ticket meanwhile. |
| `GATE PENDING` | `GATE PENDING <repository>#<n>: adversarial-review <state>: <text> (<link>)`. The repository is gated (it has `.github/workflows/review-gate.yml`, or the configuration lists it under `[review] gated`) and the commit status `adversarial-review` of the PR's head is not `success` (or the head has none: `no status posted`). The repository will refuse the merge, whatever `review=` says: a review the sweep reads as `approved-this-head` is not one the gate reads until the status is success. While it is printed the PR gets no `READY TO MERGE`. | Read the gate's text in the line. `No adversarial review yet` or a text about the form: post a new comment in the form `uvx pitboss review-form <config> <repository>` prints (a comment is never edited: the gate ignores an edited review); `Adversarial review: changes needed`: it is a fix round; any other text: read the gate run at the link. Do not merge, and do not call the review approved, until a sweep prints no `GATE PENDING` for the PR. |
| `STALL` | A relock PR (head branch starting `relock/`) whose required `check` run has been red for more than four hours (14400 seconds from the run's `completed_at`; exactly four hours is not yet one). The line says how long it has been red and, for each failing job, the names of its failed steps. A non-relock PR and a green relock PR print none, and so does a relock PR in a repository under `[merge_queue] repositories` whose failed checks all passed on the base since (`FIXED ON BASE`). | A fix, taken before every other pull request but the merge of a ready one (`rules.md`, "A free slot is filled the same turn"): root-cause the failing steps now, since the next relock fails on the same errors until the fix lands. The `FAILED` line of the same PR says more of each failed check. A stalled PR that also has `RULING DUE`, `RULING UNREADABLE`, `RULING ESCALATES`, `PAUSE` or `PLAN EDITED` waits for the ruling or the owner first (the `paused-owner` label too). At any other stage `slots next` lists the PR as `resolve the conflict`, a draft or red-CI PR included, and a ruling's own work step comes after it. |
| `UPDATE` | The PR is `behind` the base and every check of its head has finished (a behind PR whose checks still run prints none, and neither does a repository under `[merge_queue] repositories`, whose queue builds each entry on the current base). | Merge the base branch into the PR's branch (never rebase or force-push), check, push. It is not a kind in the `NEXT` list of `slots next`: that list takes the PR's kind from the flow's step alone (`pitboss next` prints the same step), and the flow has no update step. |
| `FIXED ON BASE` | `FIXED ON BASE <pr>: <check> (job N) failed at <time>, passed on the base at <time> (job M); the red CI is no work and <base> is not merged into <branch>: <action>` (keyword: fixed-on-base, pitboss#314). The repository is under `[merge_queue] repositories`, the head has no conflict, and every failed check of the head has a run on the base branch's tip that succeeded after the failed run completed (the sweep reads the base's check runs only for such a head). It stands in place of the `FAILED` lines of that head. `<action>` is `enqueue it (the merge queue tests it on main)` when the step is the merge (a review approves this exact head, or the Opus ruling does), `request the review` when the step is a review, and `next step: <the step>` otherwise. | Do what the action says. Never merge the base into the branch for this PR, and start no `fix the CI` round: the queue tests the entry on the base. A check the base has not passed since keeps its `FAILED` line, and then none of this applies. |
| `RULING DUE` | The flow's step for the PR is `OPUS_RULING` (`pitboss.flow.next_step`; `pitboss next CONFIG TICKET` prints it): the plan was rejected a second time with no ruling recorded, or the execution was rejected a second time on the approved plan after a fix round (a push that is more than a merge of the base, or an edit of the PR body: the reviews record the body's `Body:` digest, so two rejections of one head with a body fix between them count; two with nothing changed between them are one round). A review that approves the plan and asks for execution changes is not one: it is a worker round (`fix the review`). A ruling is recorded by a PR comment whose first line is exactly `Opus ruling`. The rounds are stated once, in the function (`rules.md`, "Plan first, and two rounds of changes needed"). | Start an Opus agent whose only brief is to make a ruling (the brief `pitboss next` prints, pasted unchanged but for its one `How we got here:` line, which you replace with the analysis), and record it as that comment; its ruling is taken as given. The PR is not listed in `NEXT` for a fix, an update or a review round until then, and its `STALL`, `UPDATE`, `CONFLICT` and `FAILED` lines wait for the ruling. |
| `PAUSE` | The flow's step for the PR is `PAUSE_FOR_OWNER` (`pitboss.flow.next_step`): a review asks for changes on the plan, or on the execution, and it was posted after a recorded ruling that can be read. A ruling that no review follows is never one (it is followed as `RULING ESCALATES` or by the work it names), and neither is a ruling that cannot be read (`RULING UNREADABLE`). The line ends with the count of the findings the review comments mark on lines that start with `Missed earlier:` (`adversarial-review.md`, "One round lists every finding"), as `findings the reviews mark missed earlier: <n> after the ruling, <m> before it`, counted from the trusted review comments, for the analysis of why the rounds after the ruling did not converge. | Opus never gets another shot: label the PR and its ticket `paused-owner`, comment what the rounds disagreed about and the options and a `How we got here` section, stop listing both, and report the number and the options to the owner on a card that has the section too and a markdown artifact attached with the sections `What happened`, `Recommendation` and `Suggested mitigation` (`rules.md`, "Plan first, and two rounds of changes needed" and "An escalation says how the work got there"; `uvx pitboss lint owner-card FILE` checks the card). The PR is not listed in `NEXT` for a fix, an update or a review round, and its `STALL`, `UPDATE`, `CONFLICT` and `FAILED` lines wait for the owner. |
| `RULING UNREADABLE` | `RULING UNREADABLE <repository>#<n>: <comment URL> is not in the ruling form: the second line must be 'Ruling: <word>', <word> one of: do these steps, revise the plan, execution is approved, split, reshape, abandon, escalate to the owner; ...`. The flow's step for the PR is `FIX_RULING` (`pitboss.flow.next_step`, checked right after the pause label, so a draft gets it too): the newest trusted comment whose first line is exactly `Opus ruling` has no second line `Ruling: <word>` with one of those words (a newer such comment hides an older readable ruling). The PR is not paused, and no review followed a ruling that could be read, so `PAUSE` is not printed from it. | An agent edits the comment, or posts the ruling again, with the second line exactly `Ruling: <word>`; never start another Opus agent (that is `RULING DUE`). The PR is not listed in `NEXT` for a fix, an update or a review round until the comment is in form, and its `STALL`, `UPDATE`, `CONFLICT` and `FAILED` lines wait. |
| `PLAN EDITED` | `PLAN EDITED <repository>#<n>: ...` (keyword: plan-digest, pitboss#172). The flow's step for the PR is `PLAN_EDITED`: the Plan section of the body (the `## Plan` heading to the next `## ` heading, without `Head:` lines) is not the Plan that the newest review approving the Plan and recording a `Plan digest:` line read, and no Opus ruling `revise the plan` was recorded after that review. An approved Plan is never reopened (`rules.md`, "Plan first, and two rounds of changes needed"). A review that records no `Plan digest:` line is not checked. | Restore the approved Plan text and fix the Execution against it, or start an Opus agent whose only brief is to make a ruling (`revise the plan` allows the edit). `slots next` offers the PR for no fix, review or Plan revision until then, and its `STALL`, `UPDATE`, `CONFLICT` and `FAILED` lines wait until the Plan is restored or a ruling allows the edit. |
| `PLAN ROW` | `PLAN ROW <repository>#<n>: ...` (keyword: plan-row). A numbered Plan row does not hold the command of its Evidence line; the rule, and when it does not apply, is in the help of `pitboss lint pr-body --help` (`--comments`). | Make the Plan row hold the exact command string in backticks, before a review round is requested. |
| `RULING ESCALATES` | The flow's step for the PR is `RULING_ESCALATES`: the newest ruling can be read and says `escalate to the owner`, and no review follows it. | The same as `PAUSE`: label the PR and its ticket `paused-owner`, comment the options and a `How we got here` section, stop listing both, and report the number and the options to the owner on a card that has the section too and a markdown artifact attached with the sections `What happened`, `Recommendation` and `Suggested mitigation`. The PR is not listed in `NEXT` for a round, and its `STALL`, `UPDATE`, `CONFLICT` and `FAILED` lines wait for the owner. |
| `REVIEW NOTE` | `REVIEW NOTE <repository>#<n>: ...` (keyword: review-note, pitboss#240). The newest review that counts approves, and its `Notes` paragraph (a line `Notes:` or a `Notes` heading, to the next blank line or heading) mentions `missed`, `never counted`, `not handled` or `only`. The line quotes the paragraph. A review with no such paragraph, or whose paragraph has none of the words, prints none. | Before merging, read the note. A note that names a case of the goal the change does not handle is a finding: start a fix round, never a ticket (`rules.md`, "Agents and slots"). A note that holds only what the change did not cause may stay a note. |
| `RULING NO ANALYSIS` | `RULING NO ANALYSIS <repository>#<n>: <comment URL> has no 'How we got here' section: ...` (keyword: how-we-got-here, pitboss#168). The newest trusted comment whose first line is exactly `Opus ruling` has no line that starts with the words `How we got here` (a heading, bold or a label) with anything after them. The flow is not changed by it: the ruling is read and followed as it says, and `RULING UNREADABLE` is not printed for it. | An agent edits the comment, or posts the ruling again, with the section: for each rejection before the ruling, the finding, the rule or brief line that should have prevented it, and the prevention filed (a pitboss ticket number); file a prevention that has no ticket first (`rules.md`, "An escalation says how the work got there"). The PR is not held for it. |
| `OPUS RULINGS DAILY` | `OPUS RULINGS DAILY: <n> Opus ruling comment(s) (<each comment's address>) on open, merged or closed PRs or on issues since the last summary and none recorded for today (Pacific day); ...` (keyword: ruling-summary, pitboss#237, pitboss#239). Printed once, after the slot ledger, when a trusted comment whose first line is exactly `Opus ruling` on an open, merged or closed PR or on an issue is dated after the last recorded summary and no summary is recorded for the Pacific day (`America/Los_Angeles`) of the sweep. The record is `.git/pitboss-ruling-summaries.log` of the main clone, one time with an offset for each summary. | Write the summary of every Opus ruling of the day, each with a suggested mitigation, as a markdown artifact for the owner (`rules.md`, "A question that reaches the owner comes with a markdown artifact"), then record it with `uvx pitboss ruling-summary <config>`; the sweep prints no such line again that Pacific day. |
| `WAIT-FOR-CI` | No check run of the PR's head has completed (checks not yet started or still running). It is never reviewed, approved or merged on this head, except a review of a draft at its Plan stage (its first review, or the review of a revised plan), which its author's hand-back starts (`rules.md`, "Plan first"). | Wait for CI; a reviewer started on it, other than such a draft review, reports NOT STARTED. A draft whose Plan is approved is undrafted when `can_undraft` holds (`pitboss pressure` passes), before any CI wait (a draft whose diff changes the e2e suite and has no completed dispatched run of `check.yml` at its head has `RUN E2E BEFORE APPROVAL` instead, below, but only when nothing is running at the head: while a check run of the head is unfinished it shows `waiting for CI at this head`), so its checks run (`rules.md`, "Plan first"); a draft whose Plan is not approved is never undrafted and has the `DRAFT ROUND` line instead of this one, and so has a draft whose Plan is approved when the newest review at its head asks for changes (`fix the review`, pitboss#176). |
| `FOLDED PR` | `FOLDED PR <repository>#<n>: its body closes <k> tickets (<tickets>) and cites no Opus ruling that allows it` (keyword: fold, pitboss#171). The body has `Fixes` or `Closes` lines for more than one ticket and does not cite the address of a trusted `Opus ruling` comment of the PR whose second line is `Ruling: do these steps`. | A cap on open PRs is met by finishing or closing PRs, never by folding tickets (`rules.md`, "A cap on open PRs"). Do not push or merge it: the orchestrator asks for the Opus ruling (`Ruling: split` is refused, and the tickets get a PR each), records it before the first push, and the body cites the comment's address. `uvx pitboss lint pr-body BODYFILE --ruling <comment URL> <comment file>` says whether the body is in form; the `text-lint` status of the PR (`lint event`) reads the PR's ruling comments too, and is posted again by the next edit of the body. |
| `DRAFT ROUND` | `DRAFT ROUND <repository>#<n>: <round>; ...` (keyword: draft-review, pitboss#156). A draft whose step is a round: `review it` (no review, or a review of an older head, of its Plan), `revise the plan` or `fix the review` (a review at its head asks for changes, whether or not its Plan is approved, pitboss#176). It is the line `slots next` prints for the PR, in the same words, and it replaces `WAIT-FOR-CI` for it. | Take it as the `NEXT` line says: a draft is in progress, so it is worked before any `start a PR` line. A reviewer reads the diff and the PR body only (and dry-runs the Plan's commands); the reviewer's brief from `slots next` says what else to read. |
| `RUN E2E BEFORE APPROVAL` | `RUN E2E BEFORE APPROVAL: dispatch check.yml on <branch> (<repository>#<n>); ...` (keyword: run-e2e, pitboss#199). A draft whose Plan is approved, with no completed `workflow_dispatch` run of `check.yml` at its head (its own CI run, complete and green, does not count: it ran plan and build only, quire#1038), and whose diff touches `e2e/` or a path prefix that `[sweep] run_by_e2e` lists: nothing has run its e2e. It is the `PR STATE` step in the same words, it replaces `WAIT-FOR-CI` and the undraft for it, and `slots next` prints it before any review of that PR. While a check run of the head has not finished the PR is `waiting for CI at this head`, not a second dispatch; a dispatched run of `check.yml` that finished (green or red) at the head ends the step (a dispatch of another workflow does not). | Dispatch `check.yml` on the branch (`actions_run_trigger`, not a push); no review of the PR's Execution is started, and an approval is not given, until the run of the head has completed. A review brief for such a draft says: read the dispatched run of the head; a head with no complete run is `NOT STARTED: e2e has not run at <sha>`, not a verdict. |
| `EXECUTION REVIEWED BEFORE GREEN` | `EXECUTION REVIEWED BEFORE GREEN <repository>#<n>: review <id> at <sha> does not count; <what was unfinished>; ...` (keyword: execution-before-green, pitboss#202). A trusted review comment that grades the Execution (`Execution: approved` or `changes needed`, or no `Plan:`-only form) was written, by its time, while the PR was a draft with no completed `workflow_dispatch` run of `check.yml` at the reviewed head (the draft state is read from the timeline's `convert_to_draft` and `ready_for_review` events), or while a check run of the reviewed head had not completed (a run that completed after the comment is unfinished at its time; a head with no check run has no complete run). The review is not read by the sweep, `slots next` or the flow: `review=` does not name it, and a Plan-only review (its `Plan:` line and no `Execution:` line) is not subject to it. No lint is added; the facts are read. | The Execution-stage brief says a draft, or a head with an unfinished check, is NOT STARTED, not a verdict. An owner's ruling is not given on the earlier approval. |
| `PR STATE` | `PR STATE <repository>#<n>: [draft ]next step: <words>` (keyword: red-status, pitboss#162). `slots next` prints one for every open PR that was read, so none is absent: the words of its `NEXT` line when it is offered for a round, `waiting for CI at this head`, or the text of its step (paused, ruling, plan-check, merge; a draft at the undraft or its hold has a `NEXT` line too, the first one); a PR at `PLAN_CHECK` has no `NEXT` line, and the orchestrator runs `uvx pitboss plan-check <body file>` and posts its output as a PR comment (keyword: plan-check, pitboss#192). | Read it when a PR has no `NEXT` line: it says what the PR waits for. |
| `BLOCKED` | `BLOCKED <repository>#<n>: status <context> <state> (<link>): <description>` (keyword: red-status, pitboss#162), in `slots next` and in the PR's lines of the sweep. A commit status of the head failed or errored, and no later passing check run of that name answers it. The line says `blocked by the open ticket <link> (named by ...)` for each open ticket that the status description, a label of the PR or a label of the ticket the PR fixes names (`#N`, `owner/repo#N` or an issue URL; a closed or unreadable ticket is left out), and, in `slots next`, the other open PRs on which the same status fails. For the `text-lint` context it adds the cause: `about the BODY of the PR (<first finding>)` when pitboss's lint of the body finds something, `about the PIN, not the body` when it finds nothing (the tool the workflow runs is at fault, e.g. a pin from before pitboss#171, which reads no ruling comments; a relock branch and a bot's PR are exempt from the lint, so theirs is always the pin). | Body: fix the body, and the lint runs again on the edit. Pin: fix the pin (the ticket that moves it; a pin from before pitboss#171 moves to a commit from pitboss#171 or later, and the caller grants `pull-requests: read` in the same change), and edit no body. The PR is still listed in `NEXT` for its round. The other form is `BLOCKED <ticket> by <owner/repo#n>` (keyword: ticket-blocked, pitboss#163), in `slots next` and in the sweep: a ticket that is blocked, while the ticket or PR it names is open. It has no `NEXT` line and no slot takes it. | Nothing for the blocked ticket: the next ticket takes the slot, and the blocker is worked first. When the blocker closes or merges the ticket is listed again in its place in the order. |
| `CONFLICT` | The PR has a merge conflict. | Merge the base branch into the PR's branch (never rebase or force-push someone's branch) and regenerate generated files with the project's own tooling; for a PR with a Plan or Execution body the worker also sets the body's last `Head:` line to the merge head and reruns the Plan's commands through `pitboss expand` at it (the body only, pitboss#208). A PR with `RULING DUE`, `RULING UNREADABLE`, `RULING ESCALATES`, `PAUSE` or `PLAN EDITED` waits for the ruling, the owner or the restoring of the Plan first (the `paused-owner` label too). At any other stage `slots next` lists the PR as `resolve the conflict`, a draft or red-CI PR included, and a ruling's own work step comes after it. |
| `FAILED` | The latest run of a check on the head failed (a cancelled, skipped or superseded run is not one), and the newest of the check run and the commit status of the head that answers it is the failure: a check run is answered by a passing status posted after it completed when the status's context is the check's name, or when the Actions run its `target_url` names is the check's run or a run of the same workflow file (a workflow's job `lint` that posts the context `text-lint`: the names differ, the workflow does not). In a repository under `[merge_queue] repositories`, a head whose failed checks all passed on the base since prints `FIXED ON BASE` in place of its `FAILED` lines. A later passing status prints no `FAILED` line; a status older than the failure, or one that is not `success`, does not clear it. The line says what api.github.com gives of it: the failed step names, the check output and its annotations (job logs are not downloaded, as the sandbox blocks them). | Find the root cause from that, and from the code it names. A flake is a bug, not a reason. Re-run failed jobs at most once, and only after the whole run finished. A PR with `RULING DUE`, `RULING UNREADABLE`, `RULING ESCALATES`, `PAUSE` or `PLAN EDITED` waits for the ruling, the owner or the restoring of the Plan first (the `paused-owner` label too). At any other stage `slots next` lists the PR as `resolve the conflict`, a draft or red-CI PR included, and a ruling's own work step comes after it. |
| `REMOVED FROM QUEUE` | `REMOVED FROM QUEUE <pr>: <time>, failed job of its last queue run: <job name>: <failed step>` (keyword: removed-from-queue). The PR's timeline has an `added_to_merge_queue` event and a later `removed_from_merge_queue` event as its newest queue event, it is not merged and auto-merge is off, in a repository under `[merge_queue] repositories`. The time is the removal's; the job and step are read from the jobs of the PR's newest merge group (`queue=` shows its run). With no failed job the line says `no failed job in its last queue run: cancelled by the queue`; with no run of the PR among the newest runs listed it says so, and the cause is unknown. A PR added again after the removal prints none. When the PR would get a `READY TO MERGE` or `AUTO MERGE OFF` line (nothing failing, no conflict, not a draft, and a review that approves this exact head, or the Opus ruling, or the pins-check printed OK: `PINS-ONLY OK`), the next line is `READY TO MERGE <pr>: arm auto-merge`, in place of those lines. With any other standing (a review of an older head, none, or one that asks for changes) the removal line is printed alone, with no merge action: arming auto-merge there could merge a head nobody approved. | Read the cause in the line before arming: a failed job is a `FAILED` to root-cause (a flake is a bug, and a dependency fetch failure is a ticket in the repository that owns the job), a cancelled group needs only the re-arm. Then arm auto-merge when the next line says so (never merge by hand around the queue). |
| `AUTO MERGE OFF` | A PR with nothing failing and no conflict, whose newest review approved this exact head (`review=approved-this-head`), has auto-merge off and is not in the queue. With any other review (`none`, `older-head`, `older-body`, `approved-before-merges`, `changes-needed`, `plan-changes-needed`, `plan-approved`) no line is printed: arming auto-merge there could merge a head nobody approved (a head the Opus ruling approved gets `READY TO MERGE` while auto-merge is off). | Arm auto-merge again (a push clears it). |
| `PINS-ONLY OK` | `PINS-ONLY OK <repository>#<n>: pins-check printed OK (<its last line>); no review is offered` (keyword: pins-only, pitboss#34). The PR is green and at a review step, only moves pins (its head branch starts with the `[relock] prefix`, or every path it changes is in `[relock] pin_files`), `[relock] pins_check_command` is set, and its last output line is the word OK or starts `OK:`. The PR's step is MERGE and no review is offered for it (`slots next` lists none); the next lines are its `READY TO MERGE` or `MERGE BY HAND`. | The merge, with no review (`rules.md`, "A pins-only pull request is verified by the pins-check command"). |
| `PINS-ONLY` | `PINS-ONLY <repository>#<n>: pins-check did not print OK (<line>); review it as before`. The same PR, and the command did not print OK (`NOT OK: <path>: <reason>`, a nonzero exit, a command that cannot run, a fetch that failed). A mixed PR (a path outside `pin_files` on a branch without the prefix) and a project with no command print no such line. | A review as before; for a relock PR its brief (`review the relock`) says to run the command on the head and paste its output as evidence. |
| `READY TO MERGE` | Green, `clean`, and its review approves this head (or the newest Opus ruling can be read, says `execution is approved` and no review follows it, so the flow's step is MERGE, or the pins-check printed OK: `PINS-ONLY OK`); and, in a gated repository, the head's `adversarial-review` status is success (no `GATE PENDING`); auto-merge is off. | Arm auto-merge, or merge. |
| `MERGE BY HAND` | The same, in a repository without auto-merge (for a head the Opus ruling approved the line says `execution approved by the Opus ruling`). | Merge it now, by hand: no event will arrive to say it is ready. |
| `RUNNER PRESSURE` | A merge-queue run in a repository that shares the runners has a job waiting for a runner, or the quiet period is not over (the line says the minutes remaining). | Hold (below). With an empty or absent record and nothing waiting the line says `quiet period starts now`: the sweep's look is the record's first, and the period ends that many minutes later with no one running `pressure`. |
| `NO RUNNER PRESSURE` | Nothing waits for a runner and the quiet period of `rules.md` is over (the sweep writes its look to the record: a `none` look when nothing waits, a `hold` when a job waits; `next`, `pressure` and a refused `push` write theirs too). With no `[runners]` table in the configuration the line says `no hold`: that project is on its own runner budget, nothing is held or recorded. | Push and merge as usual. |
| `QUEUE RUN` | An unfinished merge-queue run, with its age against the queue's time limit. | Nothing, unless it nears the limit while runners are short: then hold. |
| `STALE QUEUE RUN` | An unfinished run of a merge group that is no longer its PR's newest (GitHub rebuilds the groups behind a removed entry and leaves the old runs waiting). | `pitboss cancel-stale-runs <config>`, read the dry run, then again with `--no-dry-run`. If the cancel is refused, list the run ids for the owner. Never cancel a PR's newest group. |
| `CANCELLED STALE QUEUE RUN` | A stale run was cancelled (or, with "dry run", would be). | Nothing. |
| `COULD NOT CANCEL STALE QUEUE RUN` | GitHub refused the cancel. | It may have finished meanwhile; sweep again, and if it is still there, tell the owner. |
| `STRAGGLER` | A checkout on this machine with uncommitted files or commits on no remote branch. | Triage it (below). |
| `ORPHANED CHECKOUT` | A directory whose `.git` file points at a gitdir that is gone (a worktree whose main checkout was removed); git cannot read it, so it has no straggler line. | Look in the directory for files worth keeping, then delete it by hand; nothing in it is on a branch. |
| `STALE WORKTREE` | Printed only under `[clean] worktrees = "list"`: a worktree whose work is finished and on GitHub and that passes the safety test ("Stale worktrees", below). | `pitboss clean-worktrees <config>`, read the dry run, then `--no-dry-run`. |
| `REMOVED WORKTREE` | A finished worktree was removed (or, under `clean-worktrees` without `--no-dry-run`, would be); its branch is kept. A sweep prints it under `[clean] worktrees = "auto"` (the default), with the space freed on the last line of the section. Under disk pressure a merged worktree whose `.pitboss-live` marker was ignored prints `(...; its .pitboss-live marker is ignored: a worktree merged after it)`; at any disk level a merged worktree whose marker is older than 6 hours (a worker's task bound) prints `(...; its .pitboss-live marker is older than 6 hours, longer than a worker runs)`. | Nothing. |
| `KEPT WORKTREE` | A finished worktree that is not removed, with the reason: commits on no remote branch, changed tracked files, a `.pitboss-live` marker or live path or `its PR merged last` (the marker of the worktree merged last, saved under disk pressure while it is under 6 hours old), the directory the command runs in or one above it, a change within the idle hours, a link, a mount point, a checkout git cannot read, or untracked files (`git worktree remove` refuses them). | Triage it like a `STRAGGLER` when the reason is work that exists only here; otherwise nothing: it is removed by a later sweep once the reason is gone. |
| `COULD NOT REMOVE WORKTREE` | git refused (a locked worktree, for one). | Look at it: someone may still be using it. |
| `SCRATCH PR` | An open PR of a `[scratch]` repository that is not a kept fixture, in one of two forms (keyword: scratch). `SCRATCH PR owner/repo#N: run finished, close the PR and delete its branch`: every workflow run of its head has finished (a head with no run yet counts as finished once the PR is ten minutes old); printed only under `[clean] worktrees = "list"`, since the default closes it ("Scratch PRs", below). `SCRATCH PR owner/repo#N: head branch B is not one of ...; reuse one of them for the next run`: its head branch is not in `[scratch] branches`, whether its run has finished or not. A PR whose runs are still going and whose branch is a run branch prints no line, and a fixture named in `[scratch] keep` never does. | Close the PR and delete its branch, or run `pitboss clean <config>`; next time reuse a run branch. |
| `CLOSED SCRATCH PR` | A sweep (under `[clean] worktrees = "auto"`) or `pitboss clean` closed a scratch PR whose run finished. | Nothing. |
| `DELETED SCRATCH BRANCH` | The head branch of a scratch PR it closed was deleted. | Nothing. |
| `COULD NOT CLOSE SCRATCH PR` | GitHub refused to close a scratch PR; the line gives the HTTP status. | Close it by hand, or give the session the access; the next sweep tries again. |
| `COULD NOT DELETE SCRATCH BRANCH` | A branch of a closed scratch PR is still there, with the reason: another open PR has it as its head (a run branch is reused), its head is in another repository, or GitHub refused (a session may not be allowed to delete a branch). | Nothing for the first two. For a refusal, leave it: the run branches are reused, and the next run force-pushes into one ("Scratch PRs", below). |
| `clean:` | The first lines of a sweep (keyword: auto-clean): the mode (`disk under 90% used`, or `DISK OVER 90% (...)` or `DISK UNDER 5 GiB FREE (...)`: aggressive), what was removed and the space freed, what is never touched (a worktree with an open PR, a running worker's directory (a merged one's `.pitboss-live` marker counts only for 6 hours), the main clone, the directory the sweep runs in; under pressure each open-PR worktree is named), and a total. Under pressure it ends with the account below: `clean: kept PATH (WHY)` for each directory of the workspace that is not a registered worktree and was not removed (a full clone with an open PR, an unreadable checkout, `not a git checkout`); `clean: freed by kind: worktrees X, checkouts X, test tempdirs X, package caches X` ("would be freed" in a dry run); when that is less than the disk needs to get out of the pressure, `clean: X freed, X short of the X needed to get under 90%: each directory over 500 MB that was kept` (`needed to have 5 GiB free` when the free-space rule set the need) and then `clean: kept SIZE PATH (WHY): over 500 MB` for each such directory, largest first. The sweep has removed it already. | Nothing. Never ask the owner about it ("Automatic cleaning", below). |
| `DISK PRESSURE` | A filesystem of the workspace or of a `[clean] scratch` directory has less free than `[clean] min_free_gib` (default 5 GiB; 0 never warns). Under that minimum the sweep's clean is the aggressive pass, as over `pressure_percent`, for every repository the workspace holds (each directory judged by the PRs of its own `origin`, whatever config the sweep runs with). The line says how much was free, the pass it started and the bytes it freed; when the free space is still under the minimum, further lines list each directory over 500 MB that was kept, with why. | Read the kept directories; `pitboss clean-container <config>` for the dead paths ("Disk", below). |
| `DISK` | `next` and `slots next` print the free space of the workspace's volume (keyword: disk-watch, pitboss#288). From 85% used the line says to clean; from 90% used, or under 1 GiB free, the first suggestion is `clean the disk` (`uvx pitboss clean-container`, then `uvx pitboss clean-container --no-dry-run`, then the five largest `[clean] scratch` entries); under 1 GiB free no worker is suggested. | Run the two commands the suggestion names before starting a worker. |
| `REMOVED PATH` | A dead path was removed by `clean-container` (or, with "dry run", would be): its size and why it is dead. | Nothing. |
| `KEPT PATH` | A dead path with work that exists only here (commits on no remote branch, in any branch or the stash of a standalone clone; changed tracked files), or that git cannot read, a bare repository, a mount point inside it or a path that cannot be looked at; never removed. | Triage it like a `STRAGGLER`. |
| `COULD NOT REMOVE PATH` | `rm` left the path in place, the path was looked at again just before its removal and was live, busy or unsafe, or a path of the `--approved` file is not a safe dead path directly in a configured root now. | Look at it: someone may still be using it. |
| `SWEEP REMINDER` | A question each sweep ends with (the project's configuration may set its own). | Answer it before ending the sweep (below). |
| `EMPTY SLOT` | A worker slot has no agent. | See `slots.md`. |
| `SLOTS FREE` | `SLOTS FREE n`: fewer workers run than the slots configured (n of them free) and the queue has work. | Start work with `slots next`, and before the turn ends set a wake-up (`send_later`): nothing else wakes an idle orchestrator until a GitHub event. |
| `GONE AGENT` | The ledger holds an agent the session no longer runs. | See `slots.md`. |
| `CHECK BEFORE YOU ANSWER` | The ledger is kept by hand. | See `slots.md`. |
| `NEXT` | A line of the sorted list of what to start, printed by `pitboss slots next` (a sweep prints none). A draft whose Plan is approved: `mark the PR ready: update_pull_request draft=false for <PR>`, or `HOLD on undrafts ...: mark ready at <time> at the earliest` while the runners hold (pitboss#273). | See `slots.md`; mark the PR ready as the first line says. |
| `HOLD` | `HOLD new pull requests: <repository> (<n> open)`, once, while the owner's hold applies (`[holds] new_pull_requests`: more than `max_open` pull requests of a listed repository are open). | Start no new pull request in that repository: finish its open ones. `slots next` offers none of its tickets (`HELD`). |
| `HELD` | A line of `pitboss slots next`: a ticket of a held repository, `HELD (no new pull requests in <repository>: <n> open) <ticket>`. It has no `NEXT` number and no slot takes it. | Nothing: the next ticket takes the slot (`slots.md`). |
| `SUGGESTION` | A suggestion printed by `pitboss next CONFIG` and `pitboss slots next`: `SUGGESTION n of m: <kind>: <PR or ticket>: <model class>`, then the complete brief, then `--- end of suggestion n ---`; or `SUGGESTION: none` when nothing could start, or `SUGGESTION: n more queued, not shown`. | Paste the brief of the first suggestion you can start, unchanged (`rules.md`, "Briefs come from pitboss"); a ruling brief has one line, `How we got here:`, that you replace with the analysis (a fact the tool cannot know) before you send it. If the first cannot start (a missing checkout), take the next one. |
| `SLOT IDLE` | `SLOT IDLE <slot> (<n> minutes): ...`: a slot with no agent whose newest entry in the slot log (`[slots] log`) says empty over 2 minutes ago, while work is queued (the work its `EMPTY SLOT` line names). A slot the log has not seen, or a full one, has none. | Start the item the `EMPTY SLOT` line names at once; a `waiting for CI` line or any wait line is no reason to leave the slot empty (`rules.md`, "Agents and slots", 5). |
| `NO HAND-BACK` | The ledger holds an agent started more than 10 minutes ago that has produced no hand-back or notification; the line gives its minutes. | See `slots.md`. |
| `POLLING` | `POLLING <agent> on <task>: <n> tool calls, the last 20 are Monitor or sleep`: a running agent (not waiting) with over 40 tool calls whose last 20 are `Monitor` calls or `sleep` commands, read from `[slots] transcripts` (the directory of the workers' `agent-<id>.jsonl` and `.meta.json`; no line without it). | See `slots.md`. |
| `SYNCED` | A sweep (or `pitboss sync`) copied a working file that changed to `notes-current` of the `[sync]` repository's main (`SYNCED <path>`). A sweep with nothing to commit (the files are identical to the remote, or a copy stages nothing) prints `sync: nothing to commit`, makes no commit and is not an error. | Nothing. |
| `SYNC NOT CONFIGURED` | The configuration has no `[sync]` table, so nothing the orchestrator creates is kept; the line is `SYNC NOT CONFIGURED: add a [sync] table (reference: sweep.md, "The orchestrator's working files")`, and the sweep exits 1. | Add a `[sync]` table to the configuration (below), run `uvx pitboss sync <config>`, and sweep again. |
| `NOT SYNCED` | A file beside the configuration (`*.toml`, `*.tsv`, `*.md`) or named by it (the slots file, the notes) is not in `[sync] paths`, and is not one of the files the sync keeps by itself (the configuration, the ledger, the log, the record); the line is `NOT SYNCED <path>`, one for each file, and the sweep exits 1. | Add the path to `[sync] paths` in the configuration, run `uvx pitboss sync <config>`, and sweep again; or move the file out of the configuration's directory if it is not the orchestrator's. |
| `SYNC SOURCE MISSING` | A file the sync is told to keep (the configuration or a `[sync] paths` entry) is not there. | Restore it from `notes-current` of the repository (below), or take it out of `[sync] paths`. |
| `NOT THE ORCHESTRATOR CONFIG` | The first line of a sweep of a configuration that does not own the slot ledger (`[slots] ledger-owner = true`, or the path the ledger records): the slots and `NEXT` lines of that sweep are not the orchestrator list, and `slots next`, `free` and `set` refuse that configuration. The line ends with `use <path>`. | Sweep again with the configuration it names, and refill slots only from that one (`slots.md`, "Which configuration refills the slot"). |
| `INCOMPLETE` | The last line of a sweep, `slots next` or `next` that could not read a configured repository (`INCOMPLETE: N repositories unreadable: <names>; no statement about their PRs or tickets is true`), or the list of the owner's repositories (`INCOMPLETE: the repositories of <owner> were not listed (<reason>); ...`). The exit status is 1. The sweep takes every repository of `[project] owner` that is not archived and not in `[libraries] exclude`, so a repository left out of `[libraries] repositories` is swept too (keyword: repo-access, pitboss#295). | Give the session access to the repositories it names and sweep again. Until then no answer about "all PRs", counts or "nothing else is open" is given from that sweep (`rules.md`, "Agents and slots"). |
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
line, that the Evidence is real output on the head (a row the Plan points to CI
has the pointer instead), and the checks (`rules.md`,
"Reviews"). The only reads the orchestrator makes of a PR are the sweep's
markers and the review's verdict line.

## The runner-pressure hold

Runners are shared between the merge queue and everything else. While a
queue run waits for a runner, every push, new PR, merge, workflow dispatch or re-run in any
repository that shares them adds runs ahead of it, and a queue run that
waits past its time limit is dequeued (`CI_TIMEOUT`).

While `RUNNER PRESSURE` is printed:

- do not push to a non-draft PR, mark a PR ready, enqueue or merge (by hand
  or by re-arming auto-merge), dispatch a workflow (a dispatch on a draft too)
  or re-run jobs;
  pushes to a draft PR, and opening one, start no costly job and are not held;
- tell every running agent to hold its pushes to non-draft PRs and keep working locally
  (design, proofs, local checks), committing locally only; unpushed work is
  expected during a hold;
- reading runs and logs, filing and commenting on issues, and reviews that
  start no runs are fine.

A hold that is wrong because of a known pitboss bug with a ticket (pitboss#215
held pitboss's own pull requests, which use their own runner budget) is not
waited out: push with the plain `git push origin <branch>` and cite the ticket
in the same turn. No ticket yet: file it first. The bats-lang repositories keep
their hold.

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
carries `.pitboss-live` (under disk pressure that keeps a merged one only when its work merged last, and a marker older than 6 hours, the bound of a worker's task, keeps a merged one at no disk level). A worktree with an open PR is never finished. A finished worktree is
removed only when it passes the safety test, the one `clean-container` and the
sweep's clean use (the `DISK PRESSURE` line runs none, it tells what the clean did): every commit in it is on a remote branch, no tracked
file in it is changed (untracked files are scratch), nothing in it changed in the
configured idle hours (by file times, because a new worktree's tip is an old
commit), it holds no `.pitboss-live` marker (below the pressure and for a
marker under 6 hours old; the two exceptions follow) and is not a live path, it is no
link or mount point, and it is not the directory the command runs in or a
directory above it. A finished worktree that passes but holds untracked files is
kept too, with their count, because `git worktree remove` refuses it, except a
worktree whose only untracked file is a marker that was ignored (under pressure,
or because a merged worktree's marker is older than 6 hours, the bound of a
worker's task, which pitboss#194 chose), which is removed with `--force`. By default
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
more of a file system used (`[clean] pressure_percent`), or with less than 5 GiB
free on it (`[clean] min_free_gib`, `DISK PRESSURE`), it is aggressive: tempdirs
untouched for an hour, every worktree and checkout with no open PR, and the
package caches that regenerate. A worktree with an open PR, a running worker's
directory (changed within the idle hours, or marked `.pitboss-live`), the main
clone and the sweep's own directory are never touched (but under pressure a merged
worktree's marker is ignored, except the one whose PR merged last, and at any
disk level a merged worktree's marker older than 6 hours is ignored), and under
pressure every other directory of the workspace, a full clone included, is
judged by the PRs of its own `origin` and removed when its branch has none open
(the others print `clean: kept PATH (WHY)`, and the sweep ends with the bytes
freed by each kind and, short of the need, each kept directory over 500 MB), and a worktree with
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
  absent), which is judged like the others and is removed by a sweep's clean.

It is never listed when it is marked live: a file named `.pitboss-live` is in
it at any depth or in a directory above it (except in a merged checkout, where a
marker older than 6 hours is not honored), it is, holds or lies in a path of
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
