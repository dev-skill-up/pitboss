# CI rulings

These are the owner's rulings on CI, pins, caches and checking before a push.
They hold for any project on GitHub, so what names one project's own tools,
files, queue or runners stays in that project's notes. Read this file with
`rules.md` before briefing a worker whose change touches CI, a lock or a
cache.

## CI is pinned

Every input to CI is pinned in the source, so a commit that passes keeps
passing: the packages by the committed lock, the compiler by its commit, a
called workflow by its commit, and the runner image by its label. CI never
relocks: the build fetches exactly the locked versions and fails when a lock
is missing or does not match the project. A PR that adopts new package
versions relocks and commits the lock with the change that needs them. Pins
move only through a reviewed PR that runs the same CI; the daily relock is one
such PR.

The owner's ruling is that pins move from the relock alone and that no bot
opens a pull request (owner, 2026-10-23T01:15:16Z, transcript line 74799: "I
don't want these bots opening PRs. I want to do everything from relock").

## No cache key is relied on for correctness

A restored cache is judged by the tool, never by the key that found it.

## No mtimes in freshness

Nothing that decides whether an output is fresh (a build, a cache, a memo, a
test selection) reads a file's time: it compares content hashes.

## Workflow steps are not code of ours

A workflow `run:` step that does more than call one subcommand of the
project's tool or one third-party tool is code we wrote, and a PR that adds it
names the avenue it exhausted (`engineering.md`, "Our own code is in our own
language, not shell").

## Check locally before every push

Run the project's check before every push, so a push that does not pass it
never reaches CI. The check runs in a checkout that stays (the next ticket is
a new branch in it, and nobody deletes it or its build output; `rules.md`,
"Checkouts and disk"), so it is incremental. A fix pushed after a red CI is
checked the same way first.

**A run over a population is a sample.** A local run takes about 10 minutes:
the members of the population (the static fixtures, the end-to-end specs, the
mutation lemmas) are drawn at random with a seed that is printed, and the PR
says the sample, its seed and size and why it suffices; the whole population
is CI's.

## A draft PR runs no costly job

The workflow runs on a pull request's `ready_for_review` as well as GitHub's
default three types (`opened`, `synchronize`, `reopened`), so marking a PR
ready runs the check on its head. Each job that costs runner time carries
`github.event_name != 'pull_request' || !github.event.pull_request.draft`, and
the jobs that need them are skipped with them. The required check is skipped,
which GitHub counts as passed, so it is reported, not missing; a draft cannot
merge in any case. Push, `workflow_dispatch`, `schedule` and `merge_group` are
unchanged.
