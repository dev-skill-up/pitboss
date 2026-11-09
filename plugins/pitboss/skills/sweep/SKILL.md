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
it prints is hidden.

When the
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

The agent never asks the owner about cleanup: when the
classifier denies an `rm`, run `uvx pitboss clean <config>` (the allow list
covers it) and go on.

Other commands, all reading the same file:

| Command | Use |
| :--- | :--- |
| `uvx pitboss --help` |

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
runs the workers (tickets, briefs, reviews, pushing and merging), each
with his dated words. Read `references/sweep.md`: it says what each marker
means and what to do about it, including the runner-pressure hold, which comes before everything
else.
Read `references/engineering.md` (the owner's rulings on code,
tests and errors) before briefing or reviewing a change to code, and
`references/ci.md` (pins, caches, checking before a push, draft PRs, spacing CI-triggering actions under a merge queue) before
briefing a change to CI, a lock or a cache. Give `references/adversarial-review.md` to every reviewer you
start; a reviewer reads that file and nothing else about the form.

The commands that change something (`cancel-stale-runs`, `clean-worktrees`, `clean-container`)
are dry runs unless given `--no-dry-run`: run the dry run first and read
all of it. The sweep and `clean` are the exception: they have no dry run (`clean --dry-run` is the opt-in).
