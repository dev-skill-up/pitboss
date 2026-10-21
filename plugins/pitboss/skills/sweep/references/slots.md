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

Update the ledger at every spawn (`set`) and every hand-back or completion
notice (`free`).

## Markers

- `EMPTY SLOT`: the slot has no agent. In `slots show`, run `slots next`; in
  `slots next`, the line names what the slot starts, or says nothing fits
  it. Start that now, or leave the slot empty when nothing fits.
- `GONE AGENT`: the ledger holds an agent the session no longer runs. Free
  the slot with the command the line gives.
- `CHECK BEFORE YOU ANSWER`: printed after the ledger, on stderr. The ledger
  is kept by hand and goes stale. Before acting on it or reporting it, list
  the agents the session runs (the session's own agent listing; a process
  listing cannot count them, they share one process), run `slots check`
  with their names, fix the ledger with `free` and `set`, then act or answer.
- `NEXT`: one line of the sorted list.

## The order of work

1. Work in progress first: a worker on a task finishes it, unless there is
   an emergency.
2. Then pull requests in progress: an open PR with no worker that is still
   relevant is finished (fixed, reviewed, brought up to date, merged),
   whatever its priority, so open PRs do not pile up.
3. Then new work, in the order the project requires.

`slots next` sorts what it can see from GitHub into three categories, in
this order, and says on each line why it is where it is:

1. **Fix the review**: an open PR whose newest review asks for changes on
   its current head. Its author fixes it.
2. **Review it**: an open PR whose checks all finished and passed on its
   head, with no conflict, not a draft, and no review of that head. A
   reviewer that is not its author reviews it, and only once every check
   finished green on that exact head; the author never waits on CI, but
   pushes, reports the head and finishes.
3. **Start a PR**: an open ticket with one of the configured priority
   labels, that no open PR names (in its title, body or branch) and whose
   named paths no open PR changes; a ticket with none of the labels is never
   offered.

Within a category: by priority label (the order of `priority_labels`), then
oldest first by the creation time of the PR or the ticket. Items a slot
already holds are left out.

Each line names the smallest model it may go to: the first configured model
that has not failed it, and no smaller than the model a `[slots.model_labels]`
label on it names. Empty slots are filled smallest model first, each with the
first line its model may take; a review is always given to a different agent
from the PR's author. When every slot is full, start nothing.

## Briefs

A worker's brief has no exit clause. The only acceptable "not done" is "the
brief as written is impossible, because ...". Reports carry no hedges.
