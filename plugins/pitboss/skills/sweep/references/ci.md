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

## A repository with slow, costly CI and a merge queue

Where a full check takes a long time and the runners are few, CI capacity, not
the worker's time, is the constraint. The same holds for any language or
host. The rules below keep the queue's runs from waiting behind the project's
own pushes. Each says which sweep line or configuration key carries it, and
where nothing carries it, it is kept by hand and says so.

**What costs runs.** A CI-triggering action is one that starts workflow runs:
a push to a non-draft PR, marking a PR ready (undraft), enqueueing a PR,
merging into the base branch, and dispatching a workflow or re-running jobs.
Each adds runs ahead of a queue run that is already waiting for a runner, and
a queue run that waits past the queue's time limit is dequeued.

**Spacing.**
- Leave an interval between two CI-triggering actions on the project (the
  project picks it: `[runners] quiet_minutes`, the quiet period of the
  pressure rule below). Why: runs do not start the moment the action is taken, so a second
  action taken too soon is not seen by the pressure check that was meant to
  guard it (owner, 2026-10-26: "some things get a minute to trigger in a
  serial queue"), and a burst of small PRs overloads the pool for the one run
  that gates the base branch (`rules.md`, "Pushing and merging": "avoid
  bursts: CI capacity is the constraint").
- Carried by: the quiet period (`rules.md`, "Pushing and merging"):
  `pitboss queued` and `pitboss push` record each action that goes out, and
  `pitboss pressure` exits 1 until `[runners] quiet_minutes` have passed. A
  worker never sleeps to wait it out: it commits locally and hands back
  (`rules.md`, "A worker never waits for CI checks"; owner,
  2026-10-28T23:18Z: "Workers never wait on Ci. They hand back.").

**Pushes to a draft PR are free.** With the draft condition above, a push to a
draft starts no costly job, so the interval does not apply to it and a worker
keeps its work on GitHub through a draft. The lint of the body still runs on a
draft (`rules.md`, "Pushing and merging").
- Carried by: the workflow's own condition (the section above), and in the
  sweep `WAIT-FOR-CI` for a draft with no completed check run (its reviews
  at the Plan stage are the exception: `rules.md`, "Plan first") and
  `[draft]` in the PR line (`sweep.md`). The hold below leaves draft pushes alone
  (`sweep.md`, "The runner-pressure hold"; the hold line `pitboss pressure`
  prints says the same).

**Enqueue is preferred to undraft.** Undraft runs the whole check on the head
(`ready_for_review`), and the queue then tests the group again, so each spends
one of the spaced actions. When a PR could take either next, spend it on the
enqueue, the run that gates the base branch. Undraft is for a PR whose Plan is approved
and that needs a green head for the review of its Execution (a draft has
none); a PR is not sent back to draft
to be undrafted again.
- Carried by: `READY TO MERGE` and `AUTO MERGE OFF` (arm auto-merge, which
  enqueues), `MERGE BY HAND` (repositories in `[libraries] no_auto_merge`),
  and the order of work in `rules.md` ("Agents and slots": approved at its head
  and green is a merge). No line tells an undraft from an enqueue; the choice
  is the orchestrator's.

**A PR that is only behind is not pushed; a real conflict gets a merge.** A
queue builds each entry on the current base, so a PR behind the base needs no
update push, which would spend an action and re-run the check for nothing.
Only a conflict is fixed: merge the base in (never rebase or force-push),
resolve, check locally, push (`rules.md`, "Merge conflicts").
- Carried by: `[behind]` in the PR line (no `UPDATE` line for a repository
  under `[merge_queue] repositories`, `sweep.md`), and
  for a conflict `[dirty]` with `CONFLICT` and, from the queue,
  `MERGE_CONFLICT` (`sweep.md`, "Leaving the merge queue").

**When to hold under runner pressure.** While a queue run has a job waiting
for a runner, take no CI-triggering action in any repository that shares the
runners, tell running agents to hold their pushes to non-draft PRs and work locally, and file,
comment and read as usual. A hold lifts only after the quiet period
(`rules.md`, "Pushing and merging"). Then release held work one push at a time, with a
pressure look between, re-queueing the PRs dequeued by the time limit first.
Hold early too when a queue run nears the limit while runners are short, and
keep the queue short (a few entries at a time: more entries want more runners
than the pool has) with the stale runs of removed entries cancelled.
- Carried by: `pitboss pressure <config>` (exit 1 under pressure and until the
  quiet period is over), `pitboss queued <config>` and `pitboss push`, `RUNNER
  PRESSURE` and `NO RUNNER PRESSURE`, `QUEUE RUN` (age against the limit),
  `STALE QUEUE RUN` with `pitboss cancel-stale-runs`, and the keys
  `[runners] repositories` (whose queue runs count and whose actions are held;
  default the project and its libraries), `[runners] record` and `[runners]
  quiet_minutes` (the record the looks and queued jobs are written to, and the
  quiet period), and `[merge_queue] timeout_minutes` (the limit the age is shown
  against; default 60). The limit on queue entries is kept by hand: pitboss has
  no key for the entry count. Missing key, if wanted: a maximum of queue
  entries.
