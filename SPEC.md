# pitboss spec

pitboss is three things: a parser, a state machine, and actions that check state. Nothing else. No proofs,
no seeds, no effects tables. The code is `src/pitboss/`: `jsonish.py` (total JSON readers), `parse.py`,
`machine.py`, `actions.py`, `hub.py` (the one `gh` edge) and `cli.py` (argument parsing and printing).

## 1. Parser (`parse.py`)

Input: GitHub REST JSON, every list read with `--paginate`. Output: plain frozen values, no I/O.
- `Pull`: number, head sha, draft, conflict (`mergeable_state == dirty`), labels, check states
  (`green`/`red`/`pending`), changed paths, `Body` and `Thread`.
- `Body`: the tickets it fixes, whether it has `## Plan` and `## Execution`, the digest of its Plan section.
- `Thread`: the comments of trusted authors (OWNER, MEMBER, COLLABORATOR), in order, as `Review` (first line
  `Independent review ... of head <sha>: <verdict>`, with `Plan:`, `Verdict:` or `Execution:` and
  `Plan-digest:` lines), rulings (`Opus ruling`, `Ruling: <words>`) and plan checks (`Plan check: ok`).
- `Ticket`: number, open, labels, the bullets under `## Done when`.

## 2. State machine (`machine.py`)

`pull_step(Pull, Gates) -> Step` and `ticket_step(Ticket, open pulls) -> Step`, pure, first rule that holds wins:
1. the newest event is a ruling: `RULING_STEPS` ("do these steps"), `OWNER` ("escalate"), else `FIX_RULING`;
2. no Plan and Execution sections: `WORKER`; 3. conflict: `FIX_CONFLICT`; 4. a red check: `FIX_CI`;
5. no plan check: `PLAN_CHECK`, refused: `SEND_BACK_PLAN_CHECK`; 6. no review at the head: `REVIEW`;
7. the review's Plan-digest differs from the body's: `PLAN_EDITED`;
8. changes needed: `WORKER`, `OPUS_RULING` from the second rejection; plan not approved: `WORKER`;
9. approved and draft: `RUN_E2E` when it changes `e2e/` files and has no `e2e` label, else `UNDRAFT`;
10. approved, ready, all checks green: `MERGE`, else `WAIT`.
`Gates(hold, pressure, quiet)` are machine inputs: a `hold` label or gate, runner pressure or a quiet window
turn a write (`MERGE`, `UNDRAFT`, `RUN_E2E`) into `HELD`; `UNDRAFT` is exempt from pressure.
Ticket: closed `DONE`; a PR that fixes it `WAIT_FOR_PR`; else `OPEN_PR`.

## 3. Actions (`actions.py`, `hub.py`)

One verb per write: merge, undraft, update-branch, rerun, dispatch, close, label, comment, and the three comment forms the queue posts, each for one step (`review` at REVIEW, `plan-check` at PLAN_CHECK, `ruling` at OPUS_RULING). On a ticket, `pr-create` (at OPEN_PR, as a draft). `file-ticket` has no item yet, so it checks nothing. `push` is the one git write: it pushes the checked-out head to the named branch, never forced, and only when the PR is at WORKER, FIX_CI, FIX_CONFLICT, RULING_STEPS or PLAN_EDITED; `hub.Git` is its edge, with its own injected runner beside the `gh` one. `run` recomputes the
step of the PR it was given and writes only when that is a step the verb needs (`STEPS`); otherwise it returns
`Refused(wanted, found)` and writes nothing. Results are `Done` or `Refused`. Writes go through a `Hub` port;
`hub.Github` is the `gh` implementation, with the runner injected.

## 4. Tests

Build parsed values, call the function, compare; `hub.py` is tested by injecting the runner. 100% branch
coverage, nox for lint, mypy, tests and docs.
