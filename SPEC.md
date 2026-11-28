# pitboss spec

pitboss is three things: a parser, a state machine, and actions that check state. Nothing else.

## 1. Parser (`pitboss_core/parse.py`)

Input: GitHub REST JSON, every list read with `--paginate`. Output: plain frozen values, no I/O.
- `Pull`: number, head sha, draft, conflict (`mergeable_state == dirty`), labels, check states
  (`green`/`red`/`pending`), reviews, rulings, the tickets its body fixes.
- `Review`: a trusted comment (author association in the trusted set) with a first line `Independent review ... of head <sha>: <verdict>`;
  `Plan:` and `Verdict:` lines grade it.
- Rulings: `Ruling: <words>` lines (escalation: words start with `escalate`) of trusted comments.
- `Ticket`: number, open, labels, the bullets under `## Done when`.

## 2. State machine (`pitboss_core/machine.py`)

`pull_step(Pull) -> Step` and `ticket_step(Ticket, open pulls) -> Step`, pure, first rule that holds wins:
1. newest ruling escalates: `OWNER`; 2. conflict: `FIX_CONFLICT`; 3. a red check: `FIX_CI`;
4. no review naming the head: `REVIEW`; 5. the review at the head says changes needed: `WORKER`,
`OPUS_RULING` from the second rejection; 6. execution not approved: `WORKER` (plan approved) or `REVIEW`;
7. approved and draft: `UNDRAFT`; approved, ready, all checks green: `MERGE`, else `WAIT`.
Ticket: closed `DONE`; a PR that fixes it `WAIT_FOR_PR`; else `OPEN_PR`.

## 3. Actions (`pitboss_core/actions.py`)

One function per write. Each recomputes the step of the item it was given and acts only when that is its own
step; otherwise it returns `Refused(wanted, found)` and writes nothing. Writes go through a `Hub` port.
No other check.

## 4. Overlap

The existing commands keep their names and outputs. The core is added beside them; each command moves to it
in its own change, and the old module is removed one published version later.

## 5. Tests

Build parsed values, call the function, compare. No subprocess, git, network or sleep.
