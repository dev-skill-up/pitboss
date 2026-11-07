---
name: sweep
description: Check on a project's open pull requests, merge queue, local checkouts and worker slots with pitboss, and act on what each line says. Use when a session or a loop has to check on its open PRs (after a push, at a scheduled check-in, when a notification says a check failed or a PR left the merge queue), before pushing or merging while the merge queue may be short of runners, when deciding what a free worker slot should start next, and before spawning or answering about worker agents.
---

# sweep

`pitboss` reads a project's state from GitHub and from the checkouts on this
machine (for a green pins-only PR it also runs the project's
`[relock] pins_check_command` after a `git fetch`, `sweep.md`, `PINS-ONLY`), and prints one line per thing that needs a look. Every line that
calls for an action starts with a marker in capitals and says the action.

## Run it

```bash
uvx pitboss sweep <config>
```

Run pitboss as `uvx pitboss <command>` and never as `python -m pitboss` or from
an installed copy or a checkout: `uvx` resolves the newest PyPI release, which
`release.yml` publishes on every push to main, so the bugs main fixed are fixed
in what runs. (Do not copy the package into scratch space and run that; it
goes stale.) When the permission classifier denies that form, look in the
repository's Claude Code settings file's allow list for an equivalent allowed
form and run that exact string (`rules.md`, "A denied command is retried as the
allow list's equivalent"). A sweep that prints `OUTDATED` is running an older
release than PyPI's: see `references/sweep.md`.

`<config>` is the project's file: a name looks up
`.claude/pitboss/<name>.toml` in the current directory or a parent, or give a
path. It needs `gh` authenticated for every repository the file names, and
`git`. Run it bare: no `grep`, `tail` or `timeout` in front of it, so nothing
it prints is hidden. Timings go to stderr: each section ends with
`[pitboss Ns] <section>: <seconds> s, <count> commands` and the kinds of command
it ran, and a section over 30 s names the commands it waited longest for.

On the reference machine (about 9 open PRs, 3 other repositories) it ends in
under 30 s and prints its first lines (the cleaning, then each PR) within
12 s, inside the 120 s limit of an agent's foreground shell call. When the
shell tool reports `Terminated`, or the machine is slower (a slow GitHub, a very
large `/tmp`), run it in the background with the output in a file, never with
`timeout` in front, and read the file as it grows:

```
uvx pitboss sweep <config> > <scratchpad>/sweep.out 2>&1   # run_in_background: true
```

The file holds stdout and the timings together; the run is done when the shell
tool reports its exit (1 means a line to act on, not a failure to run). Do not
decide anything from a partial file, and do not start a second sweep while one
runs.

The rule, in this order (`references/rules.md`, "Agents and slots"):

1. Run `pitboss sweep` at the start of every turn and after every handback,
   before any other decision (model, task, order, slot, hold).
2. For every line it prints, read the ticket or PR it names and check its real
   state.
3. Follow the line.
4. Override a line only when it is a pitboss bug, always override when it is
   one, and file the bug as a pitboss ticket in the same turn.

The owner (2026-11-02T23:47:19Z): "Doesn't pitboss just tell you what to do?
Run it and you won't make mistakes instead of guessing". The owner
(2026-11-03T00:29:17Z): "To be clear, it's still your responsibility to do the
right thing based on pitboss data. Check the ticket/pr it talks about and see
what the state is. That does not excuse you from running it first. Only
override for bugs, but do override for bugs (and then file them)".

It reads, with two exceptions: it ends by syncing the working files to the
`[sync]` repository's main when the configuration has the table (below), and it
cleans first, by itself, with no prompt and no
dry run (the finished worktrees that pass the safety test, the dead checkouts
and the test tempdirs of `/tmp`; at 90% disk use or under 5 GiB free also every worktree and
checkout with no open PR and the package caches), and prints what it removed and
the space freed. It never touches a worktree with an open PR or a running
worker's directory. The same cleaning closes the open PRs of the `[scratch]`
repositories whose workflow runs have finished, and deletes their branches
(`rules.md`, "Scratch repositories"); a fixture the table keeps is never
touched. The agent never asks the owner about cleanup: when the
classifier denies an `rm`, run `uvx pitboss clean <config>` (the allow list
covers it) and go on.

Other commands, all reading the same file:

| Command | Use |
| :--- | :--- |
| `uvx pitboss pressure <config>` | Before a push to a non-draft PR, an undraft, an enqueue, a merge, a workflow dispatch or a re-run: records a look and prints one line; exit 1 under runner pressure and until the quiet period is over (the minutes remaining are in the line). The looks that are recorded are this one, a `sweep`'s, a `next`'s and a refused `push`'s; a configuration with no `[runners]` table is on its own runner budget and is never held. |
| `uvx pitboss queued <config>` | After a merge, an enqueue or auto-merge armed: records that a job was put on the queue, which restarts the quiet period. |
| `uvx pitboss push <config> [--draft] [--no-dry-run] [-- <git push arguments>]` | The pressure check and `git push` in one command, so the check is not left out or put in the wrong place. Under pressure or in the quiet period it prints the hold line, exits 1, pushes nothing and records the look it made (so the quiet period can end); the worker hands back at once, naming where it stopped and the SHA of what is unpushed, and never loops or sleeps for the pressure to clear (a hold that comes from a known pitboss bug with a ticket is overridden with the plain `git push origin <branch>`, the ticket cited in the hand-back). A push that goes out is recorded as a queued job. `--draft` is for a push to a draft PR: no check, nothing recorded. |
| `uvx pitboss cancel-stale-runs <config> [--no-dry-run]` | Cancel superseded merge-queue runs. |
| `uvx pitboss clean <config> [--dry-run]` | The cleaning a sweep does first, on its own: removes at once. Run it when the disk is tight or an `rm` is denied; never ask the owner. |
| `uvx pitboss clean-worktrees <config> [--no-dry-run]` | Remove the finished worktrees that pass the safety test (a sweep does the same by itself under `[clean] worktrees = "auto"`, the default). |
| `uvx pitboss clean-container <config> [--no-dry-run] [--approved FILE] [--batch N]` | List, then remove, the dead paths that fill the disk: finished checkouts, idle scratch, files the session wrote in `/`. Work that exists only here, links, mount points and anything marked live (a merged checkout's marker counts for 6 hours) are kept; each path is checked again just before its removal. |
| `uvx pitboss review-form <config> <repository>` | The form a review comment in that repository must take. |
| `uvx pitboss lint owner-card FILE` | Refuses the text of an owner decision card (its question and `reason`, saved to a file) that has no `How we got here` section. Every escalation, to an Opus ruling or to the owner, carries that section: for each rejection before it, the finding, the rule or brief line that should have prevented it, and the prevention filed (a pitboss ticket number) (`references/rules.md`, "An escalation says how the work got there"). |
| `uvx pitboss ruling-summary <config>` | Records that the daily summary of the Opus rulings was written, which ends the `OPUS RULINGS DAILY` line for the Pacific day (`references/rules.md`, "A question that reaches the owner comes with a markdown artifact"). |
| `uvx pitboss hand-back-check <file>` | Prints `ok` for a worker's hand-back saved in the file that has a `Deviations:` line (the rules of the brief the worker broke, or `none`), else the `NOT STARTED` text to send back and exit 1 (`references/rules.md`, "A hand-back has one form"; pitboss#257). |
| `uvx pitboss body-digest <file>` | The `Body: <digest>` line a review records for the PR body saved in the file (`references/adversarial-review.md`); the sweep prints `review=older-body` when the body changed after the newest review of an unmoved head. `review the fix round's findings only` is printed only after a review of changes needed of an older head. |
| `pitboss nox [-- <test modules>]` | The worker's local check in a repository whose checks are nox sessions (pitboss#210): `nox -r` for the tests of one Python version (`tests-3.13`) first, then the `skills` session, `lint` and `mypy`, in that order, stopping at the first failure with its output and a non-zero exit. It prints one line for each session that ran (name, success or failed, seconds) and, on success, that CI's `Run Nox` step is the proof of the whole suite. A worker runs it after every edit and before every push, never a targeted module or the full `nox -r`, hands back its result for the pushed head, and a Plan never names it or any nox run as its evidence (`references/rules.md`, "Briefs and workers"). |
| `uvx pitboss plan-digest <file>` | The `Plan digest: <digest>` line a review that grades the Plan records for the `## Plan` section (without its `Head:` lines) of the PR body saved in the file (`references/adversarial-review.md`); the sweep prints `PLAN EDITED` when the Plan section differs from the digest of the newest review that approved the Plan and recorded one, and no ruling `revise the plan` followed it (`references/rules.md`, "Plan first"). Exit 2 for a body with no `## Plan` section. |
| `uvx pitboss plan-check <file>` | Runs each command of the `## Plan` section of the PR body saved in the file in a scratch worktree, except a row that runs `nox`, `pitboss nox` or `uvx ... nox`, which is not run but refused with the sentence that gives the CI pointer instead (pitboss#251), before the Plan is reviewed (keyword: plan-check, pitboss#192). The orchestrator runs it on a draft whose Plan is not approved and has no clean check (step `PLAN_CHECK`) and posts the whole output as a PR comment: its first line `Plan check`, one row for each command, the `Plan digest:` line and the last line `Plan check: ok` or `Plan check: refused` (exit 1 when a row did not run, 2 for a body it cannot read). The Plan review is offered only after a trusted comment says `Plan check: ok` for the digest of the Plan now in the body (`references/rules.md`, "Plan first"). |
| `uvx pitboss next <config>` | With no ticket, what `slots next` prints: suggestions, each with the kind, the PR or ticket, the model class and the complete brief to paste unchanged (`rules.md`, "Briefs come from pitboss"); the one exception is a ruling brief's `How we got here:` line, which the orchestrator replaces with the analysis (a fact the tool cannot know). |
| `uvx pitboss next <config> <owner/repo#N>` | The one step the ticket's PR is at (`WAIT_FOR_OWNER`, WORKER with its task, UNDRAFT, `REGULAR_REVIEW` with its stage, `WAIT_FOR_UNDRAFT`, `WAIT_FOR_CI`, `OPUS_RULING`, `PAUSE_FOR_OWNER`, `FIX_RULING`, `RULING_ESCALATES`, `PLAN_EDITED`, `PLAN_CHECK`, `RUN_E2E` or MERGE), from the open PR whose body says `Fixes` or `Closes` it; for a ticket no PR fixes, its first step, preceded by a line starting MISSING NAMES (keyword: done-when-names, pitboss#231) when the ticket's Done-when names, in backticks, a `brief.Kind` member, a file path or a `pitboss` command that is not in the tree, each named in the line: do not spend a worker on that ticket; fix the ticket (name what exists; a file the ticket asks to create is named by its directory, not as a path) before the worker is started, and a worker that sees the line hands back NOT STARTED with it. The flow is `pitboss.flow.next_step` (`rules.md`, "Plan first"). |
| `uvx pitboss slots <action> <config> ...` | The worker-slot ledger and what to start next. When a worker hands back: run `uvx pitboss sweep <config>`, do what its lines say, `slots free <config> SLOT --done AGENT` (only with `--done` naming the agent that handed back) prints the refill, and every agent launched, reviews included, is recorded with `slots set ... --running` (`references/slots.md`, "When a worker hands back"). Only the config that owns the ledger refills a slot (`ledger-owner = true`, or the path the ledger records, a key put in the ledger file by hand; a ledger made before this check records none, so the orchestrator's config adds `ledger-owner = true` to its `[slots]` table once): `slots next`, `free` and `set` from another exit 1 with `not the orchestrator config: use <path>` (`references/slots.md`, "Which configuration refills the slot"). A repository under the owner's hold (`[holds] new_pull_requests`) has its tickets printed as `HELD`, never `NEXT`, and the sweep prints one `HOLD` line: start no new pull request there (`references/rules.md`, "Order of work", 6). |
| `uvx pitboss sync <config>` | Copy the working files outside any repository (configurations, ledger, log, pressure record, `[sync] paths`) to main of the `[sync]` repository; a sweep does it last. A file you create is added to `[sync] paths` in the same turn; a configuration missing at session start is restored from `notes-current` (`references/sweep.md`, "The orchestrator's working files"). |

## A line that is wrong because of a pitboss bug (pitboss#218)

Pitboss is not the final arbiter: you run it, and you may override it with a
reason. When a line of `pitboss sweep`, `pitboss next` or `pitboss push` is
wrong because of a known pitboss bug that has a ticket, override it on the
spot, cite the ticket in the same turn, and do not wait the line out; with no
ticket yet, file one first. A hold on a push that comes from such a bug is
overridden with the plain `git push origin <branch>` of the branch. Only a line
whose cause is a ticketed pitboss bug is overridden: the bats-lang
repositories keep their hold (`references/rules.md`, the rule on checking the runner pressure; `references/sweep.md`, "The runner-pressure hold").

## Before acting on any line

Read `references/rules.md`: the owner's standing rules for the session that
runs the workers (slots, tickets, briefs, reviews, pushing and merging), each
with his dated words. Read `references/sweep.md`: it says what each marker
means and what to do about it, including the runner-pressure hold, which comes before everything
else. Read `references/slots.md` before starting, stopping or reporting on
worker agents. Read `references/engineering.md` (the owner's rulings on code,
tests and errors) before briefing or reviewing a change to code, and
`references/ci.md` (pins, caches, checking before a push, draft PRs, spacing CI-triggering actions under a merge queue) before
briefing a change to CI, a lock or a cache. Give `references/adversarial-review.md` to every reviewer you
start; a reviewer reads that file and nothing else about the form.

The commands that change something (`cancel-stale-runs`, `clean-worktrees`, `clean-container`)
are dry runs unless given `--no-dry-run`: run the dry run first and read
all of it. The sweep and `clean` are the exception: they have no dry run (`clean --dry-run` is the opt-in).
