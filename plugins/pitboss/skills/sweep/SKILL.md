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

`<config>` is the project's file: a name looks up
`.claude/pitboss/<name>.toml` in the current directory or a parent, or give a
path. It needs `gh` authenticated for every repository the file names, and
`git`. Run it bare: no `grep`, `tail` or `timeout` in front of it, so nothing
it prints is hidden. Timings go to stderr.

Run it at a scheduled check-in, when a CI or merge-queue event arrives, and
after a push. It does not change by the minute; do not run it on every turn.

Other commands, all reading the same file:

| Command | Use |
| :--- | :--- |
| `uvx pitboss pressure <config>` | Before any push, PR, merge or re-run: one line, exit 1 under runner pressure. |
| `uvx pitboss cancel-stale-runs <config> [--no-dry-run]` | Cancel superseded merge-queue runs. |
| `uvx pitboss clean-worktrees <config> [--no-dry-run]` | Remove finished worktrees. |
| `uvx pitboss review-form <config> <repository>` | The form a review comment in that repository must take. |
| `uvx pitboss slots <action> <config> ...` | The worker-slot ledger and what to start next. |

## Before acting on any line

Read `references/rules.md`: the owner's standing rules for the session that
runs the workers (slots, tickets, briefs, reviews, pushing and merging), each
with his dated words. Read `references/sweep.md`: it says what each marker
means and what to do about it, including the runner-pressure hold, which comes before everything
else. Read `references/slots.md` before starting, stopping or reporting on
worker agents. Give `references/adversarial-review.md` to every reviewer you
start; a reviewer reads that file and nothing else about the form.

The commands that change something (`cancel-stale-runs`, `clean-worktrees`)
are dry runs unless given `--no-dry-run`: run the dry run first and read
all of it.
