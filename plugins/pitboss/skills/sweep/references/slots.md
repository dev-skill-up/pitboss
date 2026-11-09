# Worker slots

A slot is a place for one worker agent, with the model it runs on. The
project's configuration names the models (smallest first, under
`[slots] models`) and the slots `pitboss sweep` starts a ledger with when the
file does not exist (`[[slots.default]]`; `pitboss slots` never starts one). The ledger, a file outside the repository, records
which agent is in which slot on which task, and which models have failed
which tickets. The owner creates the ledger file and it is authoritative on
how many slots there are: when it does not exist, every `pitboss slots`
command except `report` and `time` exits 1 with `LEDGER MISSING: <path> does not exist.
It is authoritative on the slots and the owner creates it`, and writes no file.

## Which configuration refills the slot (keyword: ledger-owner)

Only the orchestrator's configuration refills a slot: the one that owns the
ledger. A configuration owns it when its `[slots]` table says
`ledger-owner = true`, or when the ledger file records its path (a `"config"`
key at the top of the JSON, next to `"slots"`, which `set` and `free` keep).
Nothing writes that key when the file is made: it is put in the file by hand.
A ledger made before this check records no path, so the orchestrator's
configuration adds `ledger-owner = true` to its `[slots]` table once; until it
does, `slots next`, `free` and `set` refuse even that configuration.
`pitboss slots next`, `slots free` and `slots set` from any other
configuration exit 1 and print `not the orchestrator config: use <path>` (the
path the ledger records; `the configuration with ledger-owner = true` when it
records none), and neither read nor change the ledger. Another configuration may name the same ledger
file and print a plausible `NEXT` list from its own repositories, but its list
leaves out what the orchestrator's puts first (a red CI, a review), so a
refill from it starts the wrong work. `pitboss sweep` from a configuration that
does not own the ledger starts with a first line `NOT THE ORCHESTRATOR CONFIG`:
its slots and `NEXT` lines are not the orchestrator list; run the sweep again
with the configuration it names before acting on them.

## Commands

| Command | Use |
| :--- | :--- |
| `pitboss slots show <config>` | Print the ledger. |
| `pitboss slots set <config> SLOT AGENT TASK` | An agent took an empty slot. `--running NAME ...` lists every agent the session runs (the session's own agent listing) and is required; `set` is refused when the slot's current holder is among them (except a fix round of the same agent, below). Record every agent you launch, reviews included, with `set`. TASK is `#12`, `name#12` or `owner/name#12`. `--kind KIND` is `start` (default), `review`, `fix` or `ruling`. The ledger and the slot log record the ticket the task works on next to TASK: the id itself for a ticket, the first `Fixes` line of the body for a PR. Refused when pitboss cannot name the ticket (not a reference, unreadable, a PR with no `Fixes` line). Refused when the slot is occupied: free it first, except that a fix round on a PR resumes the running agent: run `slots set` again with the same agent and `--kind fix`, so the round is an entry too. |
| `pitboss slots free <config> SLOT --done AGENT` | The agent AGENT handed back, finished or was stopped. `--done` is required and must name the agent the slot holds, else the command is refused and the slot keeps its agent (pitboss#227). After it empties the slot it prints the `slots next` line for that slot (what to start, with its smallest model), or `no task is waiting`. |
| `pitboss slots add <config> SLOT MODEL` | Add a slot, when the owner raises the limit. |
| `pitboss slots remove <config> SLOT` | Remove an empty slot, when the owner lowers the limit. |
| `pitboss slots failed <config> TICKET MODEL` | A model failed a ticket (a diff that is off target, or a worker that stopped midway); the ticket goes to a larger model next. |
| `pitboss slots deviation <config> TICKET FILE` | Records the `Deviation:` lines of a review comment saved in FILE (a line `none` is left out) on the ledger's line for the worker of TICKET, the `deviation <ticket>: <text>` lines `slots show` prints after the slots; a line already recorded for the ticket is not recorded again, and the lines stay when the slot is freed. Run it for every review that lists one (`references/rules.md`, "A hand-back has one form"; pitboss#257). |
| `pitboss slots check <config> --running NAME ...` | Give it the names of the agents the session runs; it prints a `GONE AGENT` line for each agent the ledger holds that is not among them. |
| `pitboss slots check <config> N` | Exits 1 and says the ledger has fewer rows when the ledger has fewer than N rows. |
| `pitboss slots heard <config> SLOT` | The agent in the slot handed back or sent a notification (it is still there): the sweep stops listing it as `NO HAND-BACK`. |
| `pitboss slots wait <config> SLOT` | The agent in the slot waits (on CI, a review or an answer) and does no work. |
| `pitboss slots resume <config> SLOT` | The agent in the slot works again. |
| `pitboss slots report <config> [--since T] [--until T]` | The share of slot time spent running, waiting and empty, for each slot and for all, in a window (ISO times, UTC when no zone; default: the first log line to now). |
| `pitboss slots time <config> [--since T] [--until T]` | The worker minutes (running, not waiting) of each ticket, summing its start, review, fix and ruling entries, with the count of `set` entries behind each total, and the median and mean over tickets. Sum per ticket, never per task id: a review or a fix round is named by its PR. |

Update the ledger at every spawn (`set`, with `--kind` review, fix or ruling when the task is not a start), every fix round that resumes a running agent (`set` again, same agent, `--kind fix`), every time an agent starts or stops
waiting (`wait`, `resume`) and every hand-back or completion notice (`free`, or `heard` when the agent stays).

## When a worker hands back

Run `pitboss sweep`, do what its lines say, `slots free` prints the refill.
Free the slot only with `--done` naming the agent that handed back, and record
every agent you launch, reviews included, with `slots set ... --running` (the
agents the session runs), so the ledger keeps the cap (pitboss#227).
`slots free <config> SLOT --done AGENT` empties the slot and prints the line `slots next`
gives that slot (the task, its step and the smallest model), or `no task is
waiting`. Start what the line says, with the brief from `slots next`, and the
model it names; do not choose the next task or its model from your own list.

## The slot log

Every change that leaves a slot in a different state (running, waiting or
empty), with a different agent, task, ticket or kind, is also one JSON line,
and so is every `slots set`, even when it equals the slot's last line (a fix
round that resumes the agent), in the slot log (`[slots] log`, default: the ledger's name ending in `.log`):
UTC time, slot, state, agent, task, ticket and kind. A slot the log has not seen yet is
logged in the state it is in, so the time before its first change counts. A
removed slot is logged as `removed`, after which it has no slot time.
`slots report` and `slots time` replay the log, so idle and waiting time are measured, not
estimated; the sweep reads it too, for `SLOT IDLE`.

## Markers

- `EMPTY SLOT`: the slot has no agent. In `slots show`, run `slots next`; in
  `slots next`, the line names what the slot starts, or says nothing fits
  it. Start that now, or leave the slot empty when nothing fits.
- `SLOTS FREE`: `SLOTS FREE n`,
  require a
  wake-up (`send_later`) before the turn ends: an orchestrator that ends its
  turn with free slots and queued work sleeps until a GitHub event.
- `SLOT IDLE`: `SLOT IDLE <slot> (<n> minutes)`, printed by `sweep` for a slot
  that has been empty for more than 2 minutes by the slot log while work is
  queued. Start the item its `EMPTY SLOT` line names now: a `waiting for CI`
  line is no reason to leave the slot empty (`rules.md`, "Agents and slots", 5).
- `GONE AGENT`: the ledger holds an agent the session no longer runs. Free
  the slot with the command the line gives.
- `CHECK BEFORE YOU ANSWER`: printed after the ledger, on stderr. The ledger
  is kept by hand and goes stale. Before acting on it or reporting it, list
  the agents the session runs (the session's own agent listing; a process
  listing cannot count them, they share one process), run `slots check`
  with their names, fix the ledger with `free` and `set`, then act or answer.
- `NO HAND-BACK`: the sweep prints `NO HAND-BACK name (n minutes)` for an
  agent the ledger holds (`set` records its start time) that has produced
  no hand-back or notification within 10 minutes. Find out whether it is
  still running (the session's agent listing); message it, or `free` the
  slot and restart the work if it ended without a hand-back. An agent that
  has answered but stays in the slot is marked with `heard`.
- `POLLING`: the sweep prints `POLLING name on task: n tool calls, the last 20
  are Monitor or sleep` for a running agent with over 40 tool calls whose last
  20 are `Monitor` calls or `sleep` commands (each a model turn spent waiting;
  pitboss#175). Message it to run `pitboss nox` in one foreground command under
  `timeout 598`, or one `Monitor` with an `until` loop. It needs
  `[slots] transcripts`, the directory of the workers' transcripts; the agent's
  name in the ledger is the `name` in the transcript's `.meta.json`.

## The order of work

1. Work in progress first: a worker on a task finishes it, unless there is
   an emergency.
2. Then pull requests in progress: an open PR with no worker that is still
   relevant is finished (fixed, reviewed, brought up to date, merged),
   whatever its priority, so open PRs do not pile up. A `STALL` fix comes
   before every other pull request but the merge of a ready one (`rules.md`), unless the stalled PR has `RULING DUE`, `RULING UNREADABLE`, `RULING ESCALATES`, `PAUSE` or `PLAN EDITED`.
   A pull request whose flow step is `OPUS_RULING`, `PAUSE_FOR_OWNER`, `FIX_RULING`, `RULING_ESCALATES` or `PLAN_EDITED`
   (`RULING DUE`, `RULING UNREADABLE`, `RULING ESCALATES`, `PAUSE` or `PLAN EDITED` in the sweep; `pitboss.flow.next_step`) is not offered for any round until
   the ruling is recorded, the owner decides or the approved Plan is restored.
3. Then new work, in the order the project requires.

`slots next` sorts what it can see from GitHub into one list and says on each
line why it is where it is. The open pull requests that the flow's step gives a
round come first, in one list, oldest first by creation time, whatever each
needs; a line says which kind it is. The kind is the step alone
(`pitboss.flow.next_step`; `pitboss next` prints the same step), so a PR has
exactly one step and at most one kind.

1. **Revise the plan**: step WORKER, task `REVISE_PLAN`. Its author edits the
   `## Plan` section of the body (and, at the end, its `Head:` line) and nothing else (`rules.md`, "Plan first"):
   the code, docs and tests are not touched until the plan is approved.
2. **Fix the review**: step WORKER (`FIX_EXECUTION`): a
   review asked for changes to the execution. Its author fixes it.
3. **Fix the CI**: step WORKER, task `FIX_CI`: the checks of the head are
   red, which is no rejection. Its author fixes them, unless the PR waits for a
   ruling or the owner (`RULING DUE`, `PAUSE`, `RULING ESCALATES`; pitboss#183),
   and unless the PR is in a repository under `[merge_queue] repositories` and
   every failed check passed on the base since (`FIXED ON BASE`, pitboss#314):
   its step is then the one a green head has.
4. **Write the Plan and Execution body**: step WORKER, task `FIRST_ROUND`:
   the PR has no such body. Its author writes it. A relock PR (head branch
   starting with `[relock] prefix`, default `relock/`) fixes no ticket and is
   never asked for this body: it goes straight to the pins-check command
   (`rules.md`, "A pins-only pull request is verified by the pins-check
   command"), and when that does not print OK to its review, whose kind is
   `review the relock` (`pitboss#126`; the brief states the goal, that moves of
   pins are safe when the lock matches and CI is green, the check list, and that
   the reviewer runs the project's pins-check command on the head and pastes its
   output).
5. **Resolve the conflict**: step WORKER, task `RESOLVE_CONFLICT`: the head
   conflicts with the base, at every stage (a draft and a red CI included; it
   comes before the draft, CI and review gates). Not while the PR waits: the
   `paused-owner` label, `RULING UNREADABLE`, `RULING DUE`, `PAUSE`,
   `RULING ESCALATES` and `PLAN EDITED` come first, and the conflict waits for
   the ruling, the owner or the restoring of the approved Plan. A ruling's own work step comes after the conflict. Its author resolves
   it, and for a PR with a Plan or Execution body also sets the body's last `Head:` line to the merge
   head and reruns the Plan's commands through `pitboss expand` at it (the body only, pitboss#208).
6. **Do the ruling's steps**: step WORKER, task `RULING_STEPS`: the newest
   readable Opus ruling says `do these steps` and no review follows it. Its
   author does exactly those steps (the ruling is taken as given).
7. **Carry out the ruling**: step WORKER, task `RULING_AS_GIVEN`: the ruling
   says `split`, `reshape` or `abandon`. Its author does what it says to the
   ticket and the PR. (`revise the plan` is the first kind above.)
8. **Review it**: step `REGULAR_REVIEW`. On a PR that is not a draft it comes
   only once every required check finished green on the head (the CI gate); it
   is the plan-only review too when the newest review rejected the Plan and no
   review names this head or body (pitboss#167), and its brief then reads the
   checks. On a draft it is the plan-only review (stage `grade the Plan ONLY`), listed
   for a draft with no review, or one of an older head,
   and before every `start a PR` line (pitboss#156; a draft whose Plan a review at its head
   rejects is `revise the plan` or `fix the review`, and so is a draft whose Plan is approved
   when the newest review at its head asks for changes, pitboss#176; a draft whose Plan is approved
   and has no such review, and whose newest review did not approve the Plan alone after the newest readable ruling (kind 9), waits for its undraft and is offered for no round (so is one whose diff changes the e2e suite and has no completed dispatched run of `check.yml` at its head: its step is `RUN E2E BEFORE APPROVAL`, the dispatch, pitboss#199, when nothing is running at the head; while a check run of the head is unfinished it is `waiting for CI at this head`); a draft or a PR with no review whose Plan has commands and no trusted
   PR comment records a clean `plan-check` of it is at `PLAN_CHECK` and is offered for no round until the orchestrator has run
   `uvx pitboss plan-check` and posted its output as a PR comment, keyword: plan-check, pitboss#192). Its brief (the Plan stage's alone: an Execution-stage brief says a draft is NOT STARTED, pitboss#202) says the
   reviewer reads the diff and the PR body only, besides the read-only dry runs of the
   Plan's commands. A reviewer that is not its author
   reviews it; the author never waits on CI, but pushes, reports the head and
   finishes.
9. **Run the Plan's commands and fill the Execution**: step WORKER, task
   `RUN_PLAN` (pitboss#201): the newest review that counts approved the Plan
   alone (a `Plan:` line and no graded `Execution:` line) and was written after
   the newest readable Opus ruling, on a draft and on a PR that is not a draft
   alike. The ruling's round rewrote the Plan and left the Execution unrun, so
   its author runs each command of the Plan as written and fills the Execution
   and Evidence of the body, and does not change the Plan. The edit of the body
   ends the round: the review no longer counts (its `Body:` digest), so the
   Plan review is not offered again and a draft goes on to its undraft. A Plan
   approved alone with no ruling before the review is the ordinary draft's and
   is not changed.

A PR with `RULING DUE`, `RULING UNREADABLE`, `RULING ESCALATES`, `PAUSE` or `PLAN EDITED` (`sweep.md`) is none of these: it has no
line in this list, whatever its state, and a fix or a review of it
waits for the ruling or the owner.

nobody guesses which files a
ticket will touch, and no ticket is skipped or held back because another PR
might touch the same files. The one thing that keeps a ticket back is the
owner's hold on a repository (`rules.md`, "Order of work", 6): the configuration
lists it under `[holds] new_pull_requests` (with `max_open = N` to hold only
while more than N of its pull requests are open), and `slots next` prints each
of its tickets as `HELD (no new pull requests in <repository>: <n> open)
<ticket>` instead of a `NEXT` line. A `HELD` line is not numbered and is
offered to no slot; the next ticket takes the slot. The pull requests of the
repository are listed as always. The sweep prints one `HOLD` line while a
hold applies (`HOLD new pull requests: <repository> (<n> open)`). No stacking: every PR starts from the base
branch, never from another PR's branch. When a PR that merged first makes
another conflict, the conflicted PR merges the base branch in when it needs
to (see `CONFLICT` in `sweep.md`).

Each line names the smallest model it may go to: the first configured model
that has not failed it, and no smaller than the model a `[slots.model_labels]`
label on it names. Empty slots are filled smallest model first, each with the
first line its model may take; a review is always given to a different agent
from the PR's author. When every slot is full, start nothing.

## Briefs

A worker's brief has no exit clause. The only acceptable "not done" is "the
brief as written is impossible, because ...". Reports carry no hedges.

Briefs come from `pitboss next` and `pitboss slots next` and are pasted
unchanged (`rules.md`, "Briefs come from pitboss"), but for a ruling brief's
`How we got here:` line, which the orchestrator replaces with the analysis. A reviewer brief for a
line of `slots next` of the kind review it is sent as the suggestion prints it: the orchestrator reads no PR body, diff or evidence first, and
the reviewer checks the Head line, the Evidence and the checks (`rules.md`,
"Reviews").
