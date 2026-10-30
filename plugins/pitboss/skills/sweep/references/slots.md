# Worker slots

A slot is a place for one worker agent, with the model it runs on. The
project's configuration names the models (smallest first, under
`[slots] models`) and the slots a new ledger starts with
(`[[slots.default]]`). The ledger, a file outside the repository, records
which agent is in which slot on which task, and which models have failed
which tickets.

## Commands

| Command | Use |
| :--- | :--- |
| `pitboss slots show <config>` | Print the ledger. |
| `pitboss slots set <config> SLOT AGENT TASK` | An agent took an empty slot. TASK is `#12`, `name#12` or `owner/name#12`. Refused when the slot is occupied: free it first. |
| `pitboss slots free <config> SLOT` | The agent finished or was stopped. |
| `pitboss slots add <config> SLOT MODEL` | Add a slot, when the owner raises the limit. |
| `pitboss slots remove <config> SLOT` | Remove an empty slot, when the owner lowers the limit. |
| `pitboss slots failed <config> TICKET MODEL` | A model failed a ticket (a diff that is off target, or a worker that stopped midway); the ticket goes to a larger model next. |
| `pitboss slots check <config> --running NAME ...` | Give it the names of the agents the session runs; it prints a `GONE AGENT` line for each agent the ledger holds that is not among them. |
| `pitboss slots next <config>` | The sorted list of what to start, and what each empty slot takes. |
| `pitboss slots heard <config> SLOT` | The agent in the slot handed back or sent a notification (it is still there): the sweep stops listing it as `NO HAND-BACK`. |
| `pitboss slots wait <config> SLOT` | The agent in the slot waits (on CI, a review or an answer) and does no work. |
| `pitboss slots resume <config> SLOT` | The agent in the slot works again. |
| `pitboss slots report <config> [--since T] [--until T]` | The share of slot time spent running, waiting and empty, for each slot and for all, in a window (ISO times, UTC when no zone; default: the first log line to now). |

Update the ledger at every spawn (`set`), every time an agent starts or stops
waiting (`wait`, `resume`) and every hand-back or completion notice (`free`, or `heard` when the agent stays).

## The slot log

Every change that leaves a slot in a different state (running, waiting or
empty), with a different agent or on a different task, is also one JSON line
in the slot log (`[slots] log`, default: the ledger's name ending in `.log`):
UTC time, slot, state, agent and task. A slot the log has not seen yet is
logged in the state it is in, so the time before its first change counts. A
removed slot is logged as `removed`, after which it has no slot time.
`slots report` replays the log, so idle and waiting time are measured, not
estimated.

## Markers

- `EMPTY SLOT`: the slot has no agent. In `slots show`, run `slots next`; in
  `slots next`, the line names what the slot starts, or says nothing fits
  it. Start that now, or leave the slot empty when nothing fits.
- `SLOTS FREE`: `SLOTS FREE n`, printed by `sweep` after the ledger when n slots
  have no agent and the queue has work. Start work for them, and require a
  wake-up (`send_later`) before the turn ends: an orchestrator that ends its
  turn with free slots and queued work sleeps until a GitHub event.
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
- `NEXT`: one line of the sorted list.

## The order of work

1. Work in progress first: a worker on a task finishes it, unless there is
   an emergency.
2. Then pull requests in progress: an open PR with no worker that is still
   relevant is finished (fixed, reviewed, brought up to date, merged),
   whatever its priority, so open PRs do not pile up. A `STALL` fix comes
   first among the fixes (`rules.md`).
3. Then new work, in the order the project requires.

`slots next` sorts what it can see from GitHub into four categories, in
this order, and says on each line why it is where it is:

1. **Fix the review**: an open PR whose newest review asks for changes on
   its current head. Its author fixes it.
2. **Update**: an open PR whose mergeable state is `behind` and whose checks
   have all finished. Its author merges the base in, checks, and pushes (never
   a rebase or force-push). A behind PR whose checks still run is not listed.
   A repository listed under `[merge_queue] repositories` is never offered
   an update: its queue builds each entry on the current base.
3. **Review it**: an open PR whose checks all finished and passed on its
   head, with no conflict, not a draft, and no review of that head (a draft's
   first review is started by its author's hand-back, `rules.md`, "Plan
   first"). A
   reviewer that is not its author reviews it, and only once every check
   finished green on that exact head; the author never waits on CI, but
   pushes, reports the head and finishes.
4. **Start a PR**: an open ticket with one of the configured priority
   labels that no open PR names (in its title, body or branch); a ticket
   with none of the labels is never offered.

Within a category: by priority label (the order of `priority_labels`), then
oldest first by the creation time of the PR or the ticket. Items a slot
already holds are left out. A `STALL` line of the sweep (`rules.md`) is the one
exception: its fix is taken before every line of this list.

Take the lines in this order (a `STALL` fix first) and nothing else: nobody guesses which files a
ticket will touch, and no ticket is skipped or held back because another PR
might touch the same files. No stacking: every PR starts from the base
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
