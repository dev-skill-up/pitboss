---
name: sweep
description: Check on a project's open pull requests, merge queue, local checkouts and worker slots with pitboss, and act on what each line says. Use when a session or a loop has to check on its open PRs (after a push, at a scheduled check-in, when a notification says a check failed or a PR left the merge queue), before pushing or merging while the merge queue may be short of runners, when deciding what a free worker slot should start next, and before spawning or answering about worker agents.
---

# sweep

`pitboss` reads a project's state from GitHub and from the checkouts on this
machine, and prints one line per thing that needs a look. Every line that
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
it prints is hidden. Timings go to stderr.

Run it at a scheduled check-in, when a CI or merge-queue event arrives, and
after a push. It does not change by the minute; do not run it on every turn.
It reads, with two exceptions: it ends by syncing the working files to the
`[sync]` repository's main when the configuration has the table (below), and it
cleans first, by itself, with no prompt and no
dry run (the finished worktrees that pass the safety test, the dead checkouts
and the test tempdirs of `/tmp`; at 90% disk use also every worktree and
checkout with no open PR and the package caches), and prints what it removed and
the space freed. It never touches a worktree with an open PR or a running
worker's directory. The agent never asks the owner about cleanup: when the
classifier denies an `rm`, run `uvx pitboss clean <config>` (the allow list
covers it) and go on.

Other commands, all reading the same file:

| Command | Use |
| :--- | :--- |
| `uvx pitboss pressure <config>` | Before a push to a non-draft PR, an undraft, an enqueue, a merge or a re-run: records a look and prints one line; exit 1 under runner pressure and until the quiet period is over (the minutes remaining are in the line). |
| `uvx pitboss queued <config>` | After a merge, an enqueue or auto-merge armed: records that a job was put on the queue, which restarts the quiet period. |
| `uvx pitboss push <config> [--draft] [--no-dry-run] [-- <git push arguments>]` | The pressure check and `git push` in one command, so the check is not left out or put in the wrong place. Under pressure or in the quiet period it prints the hold line, exits 1, pushes and records nothing; the worker hands back at once, naming where it stopped and the SHA of what is unpushed, and never loops or sleeps for the pressure to clear. A push that goes out is recorded as a queued job. `--draft` is for a push to a draft PR: no check, nothing recorded. |
| `uvx pitboss cancel-stale-runs <config> [--no-dry-run]` | Cancel superseded merge-queue runs. |
| `uvx pitboss clean <config> [--dry-run]` | The cleaning a sweep does first, on its own: removes at once. Run it when the disk is tight or an `rm` is denied; never ask the owner. |
| `uvx pitboss clean-worktrees <config> [--no-dry-run]` | Remove the finished worktrees that pass the safety test (a sweep does the same by itself under `[clean] worktrees = "auto"`, the default). |
| `uvx pitboss clean-container <config> [--no-dry-run] [--approved FILE] [--batch N]` | List, then remove, the dead paths that fill the disk: finished checkouts, idle scratch, files the session wrote in `/`. Work that exists only here, links, mount points and anything marked live are kept; each path is checked again just before its removal. |
| `uvx pitboss review-form <config> <repository>` | The form a review comment in that repository must take. |
| `uvx pitboss next <config>` | With no ticket, what `slots next` prints: up to five ranked suggestions, each with the kind, the PR or ticket, the model class and the complete brief to paste unchanged (`rules.md`, "Briefs come from pitboss"). |
| `uvx pitboss next <config> <owner/repo#N>` | The one step the ticket's PR is at (`WAIT_FOR_OWNER`, WORKER with its task, UNDRAFT, `REGULAR_REVIEW` with its stage, `WAIT_FOR_UNDRAFT`, `WAIT_FOR_CI`, `OPUS_RULING`, `PAUSE_FOR_OWNER` or MERGE), from the open PR whose body says `Fixes` it; for a ticket no PR fixes, its first step. The flow is `pitboss.flow.next_step` (`rules.md`, "Plan first"). |
| `uvx pitboss slots <action> <config> ...` | The worker-slot ledger and what to start next. |
| `uvx pitboss sync <config>` | Copy the working files outside any repository (configurations, ledger, log, pressure record, `[sync] paths`) to main of the `[sync]` repository; a sweep does it last. A file you create is added to `[sync] paths` in the same turn; a configuration missing at session start is restored from `notes-current` (`references/sweep.md`, "The orchestrator's working files"). |

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
