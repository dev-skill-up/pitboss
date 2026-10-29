Design
======

pitboss is the ``qsweep`` and ``slots`` tools of quire#573, rebuilt as one
Python package that knows nothing about any one project. It starts from the
design comment of 2026-10-18 on that issue, with the later comments folded
in, and one change of principle: **every value that named quire, bats,
pwa, their libraries, their models, their review format or their machine
is read from the project's configuration file.** The code, its defaults,
the example configuration and the skill hold only what GitHub, git and
Claude Code define; the table below is the only place those projects are
named, as the record of where each value went.

What was project-specific, and where it went
--------------------------------------------

.. list-table::
   :header-rows: 1

   * - In ``qsweep``, ``slots`` or the 2026-10-18 design
     - In pitboss
   * - ``bats-lang/quire``
     - ``[project] owner``, ``repository``
   * - the base branch ``main`` (in ``origin/main`` and
       ``gh-readonly-queue/main/...``)
     - ``[project] base_branch`` (default ``main``)
   * - ``/home/user/quire``, ``/home/user``
     - ``[project] main_clone``, ``workspace``
   * - ``arith array sha256 zip dom bridge gestures``
     - ``[libraries] repositories`` (``name`` for the project's owner, or
       ``owner/name``)
   * - bridge has no auto-merge
     - ``[libraries] no_auto_merge``
   * - bridge, pwa and capacitor-plugins need a review of the exact head
     - ``[review] gated``
   * - ``OWNER``, ``MEMBER``, ``COLLABORATOR``
     - ``[review] trusted_associations`` (this is the default)
   * - ``## Adversarial review``, ``Reviewed: <sha>``, ``Verdict: approved``
       and the ungated ``Independent review ... of head <sha>: approved``
     - ``[review.form]`` and ``[review.gated_form]``: line templates with
       ``{sha}`` and ``{verdict}``, and the two verdict words. The default
       form is ``## Review`` / ``Reviewed: {sha}`` / ``Verdict: {verdict}``
       with ``approved`` and ``changes needed``; ``gated_form`` defaults to
       ``form``
   * - an approval survives a merge of main, except in gated repositories
     - built in: it is what "gated" means
   * - the 20 shared runners, and which repositories share them
     - ``[runners] repositories`` (default: the project and its libraries)
   * - a queue run's 60 minute limit
     - ``[merge_queue] timeout_minutes``
   * - three hours of idleness before a worktree is stale
     - ``[worktrees] idle_hours``
   * - ``/tmp/claude-0/slots.tsv``
     - ``[slots] ledger`` (default ``<main_clone>/.git/pitboss-slots.json``:
       per clone, never committed); the slot log beside it is ``[slots] log``
       (default: the ledger's name ending in ``.log``)
   * - ``sonnet1 sonnet2 haiku1``, and "haiku before sonnet"
     - ``[slots] models`` (smallest first) and ``[[slots.default]]`` (the
       name and model of each slot). Neither has a default: how many slots
       there are and what runs in them is the project's, and ``slots add``
       and ``slots remove`` change the count later
   * - ``p0 p1 p2``, p3 never
     - ``[slots] priority_labels`` (default none): a ticket with none of
       them is never offered
   * - "a ticket marked as needing a Sonnet"
     - ``[slots] model_labels``: a label that names the smallest model a
       ticket may go to
   * - the two ``SWEEP REMINDER`` questions
     - ``[sweep] reminders`` (the two questions are the default)
   * - ``.claude/pitboss/quire.toml``
     - a project checks in its own file; pitboss ships only
       ``doc/example.toml``

Three more things in the earlier design were quire's in a less obvious way,
and changed:

* ``references/adversarial-review.md`` was to hold "the exact form of the
  review comment". The form is the project's (it is in the config), so the
  reference explains how a review is read and tells the reviewer to run
  ``pitboss review-form CONFIG REPOSITORY``, which prints the form that
  repository's reviews must take, filled in from the config.
* The order work is taken in (``slots next``) said "p0 before p1 before p2".
  The order inside the third category is ``priority_labels``; nothing in the
  code or the references names a label.
* ``slots check`` was to list agents "the session no longer runs". Only the
  session can see its agents (``ListAgents``; subagents share one process,
  so ``ps`` cannot count them), so the session passes the names it sees:
  ``slots check CONFIG --running NAME ...``.

Nothing else in the code is a choice: the merge-queue branch shape
(``gh-readonly-queue/<base>/pr-<n>-<sha>``), the check-run conclusions that
count as failed (``failure``, ``timed_out``, ``action_required``,
``startup_failure``; a ``cancelled``, ``skipped`` or ``neutral`` run is not
one, since a concurrency group cancels the run it supersedes), the dequeue reasons and
``mergeable_state`` values are GitHub's.

The configuration file
----------------------

``CONFIG`` on every command is a path, or a name that resolves to
``.claude/pitboss/<name>.toml`` in the current directory or the nearest
parent that has one. ``doc/example.toml`` lists every key with its default.
Only ``[project] owner``, ``repository`` and ``main_clone`` are required.

Commands
--------

.. list-table::
   :header-rows: 1

   * - Command
     - What it does
   * - ``sweep CONFIG``
     - The read-only report, in order: the project's PRs, the libraries'
       PRs, runner pressure, queue runs, stragglers, worktrees, the
       reminders, the slots. Exits 1 when a PR has a failed check or a
       merge conflict.
   * - ``pressure CONFIG``
     - Only the runner-pressure line; exits 1 under pressure.
   * - ``cancel-stale-runs CONFIG``
     - Cancels the queue runs that are not the newest of their PR. Dry run
       unless ``--no-dry-run``.
   * - ``clean-worktrees CONFIG``
     - Removes stale worktrees, then ``git worktree prune``; branches are
       kept. Dry run unless ``--no-dry-run``.
   * - ``analyze-red CONFIG REPOSITORY WORKFLOW``
     - Read-only on GitHub (pitboss#8). Writes ``--output``, one Markdown
       file: the summary table of the red runs (failure, timed_out,
       startup_failure) of the workflow in the window (``--last N`` newest
       runs, or ``--since`` and ``--until`` days), then the causes (bursts
       of reds that share a step and error text within six hours or a PR;
       every percentage by run and by cause), the costs (failed job-minutes,
       largest runs, per class, extra runs per PR, red to fix push, fix push
       to green, and red to green labelled as the scheduling measure), the
       synthesis (the three largest changes, none whose cost is above what
       CI took to show the failure), a page for each red run, and the open
       p0 tickets with the runs that cite each. A page holds what has a
       fixed answer (job, step and timestamps, the first error line, the
       class where a rule decides it, the cost line, the next run, the
       fix commit, the known-bad count, what the pushing worker ran from the
       transcript under ``--transcripts``) and a fixed prompt, filled with
       those facts, for what needs judgement. The class list is fixed
       (``redshapes.RedClass``).
   * - ``clean-container``
     - Removes the regular files directly in ``--root`` (default ``/``)
       modified more than ``--hours`` (default 1) after ``--marker``
       (default ``/container_info.json``, the one file a Claude Code on
       the web container starts with there). Subdirectories are not
       searched; symbolic links, directories and other entries are left
       alone. Needs no configuration. Dry run unless ``--no-dry-run``.
   * - ``review-form CONFIG REPOSITORY``
     - Prints the form a review comment in that repository must take.
   * - ``slots show|set|free|add|remove|failed|check|next CONFIG ...``
     - The worker-slot ledger, and the sorted list of what to start next.

Reads go through gather's ``args.safe_run``; every change on GitHub or to
git (cancelling a run, removing a worktree) goes through ``args.run``, so it
happens only with ``--no-dry-run``. ``slots`` writes its own ledger.

Every command first reads each configured repository once; one the session
cannot read is reported as ``UNREADABLE`` and left out, so one missing grant
does not stop a sweep. Only the project's own repository is required.

How each part decides
---------------------

**Pull requests.** One request for the PR list, then, per PR, its details,
its comments and reviews, and one request for its head's check runs, all PRs
at once in a thread pool. Only the latest run of each check name on the PR's
current head counts: a run of another head is dropped, and of two runs of one
name the one that started later (then the higher id) stands, so a cancelled
or superseded run never shows as failed. A line shows ``mergeable_state``, auto-merge,
pending checks, the failed checks with their job ids, the PR's place in the
merge queue (from the ``merge_group`` runs: ``queued``, ``in_progress``, or
the newest run's conclusion), and the review's standing. Action lines follow:
``CONFLICT``, ``FAILED`` (one line for each failed check, saying why from
api.github.com only: the names of the job's failed steps, the check run's
output title and summary, and its failure annotations, cut to 300 characters;
no job log is downloaded, because the log is a redirect to blob storage that a
sandbox may block), then ``READY TO MERGE`` (checks all finished and
none failed, state ``clean``, an approving review of this head, or for an
ungated repository of an older head when everything since is merges of the
base branch) or, in a ``no_auto_merge`` repository, ``MERGE BY HAND``, or
else ``AUTO MERGE OFF`` for a healthy PR with auto-merge off, not in the
queue and not asked for changes.

**Reviews.** A review is the newest comment by a trusted author whose lines
match the repository's form. In a gated repository the form is strict: the
first line is exactly the first template line, each template line matches
exactly one line, and the comment is ASCII with no code fence, HTML or link
definition. A GitHub review (``APPROVED`` or ``CHANGES_REQUESTED`` on a
``commit_id``) by a trusted author counts too, except in a gated
repository, where only the comment form does. For an ungated repository an
approval of an older head carries over when the commits since are all
merges (the non-merge commits of ``base...head`` are those of
``base...reviewed``).

**Runner pressure.** Under pressure when any ``merge_group`` run, queued or
in progress, in any ``[runners] repositories``, has a job still ``queued``.

**Queue runs.** The unfinished ``merge_group`` runs of every repository
read; a run is stale when its merge group (its ``gh-readonly-queue`` branch)
is not its PR's newest. Runs of the newest group are never stale, one per
workflow. A live run is reported with its age against ``timeout_minutes``.

**Stragglers.** Every git checkout directly under ``workspace``: uncommitted
files, and commits on no remote branch. Each repository is fetched once.

**Worktrees.** A worktree of ``main_clone`` is stale when all of these
hold: it is not the main clone and is under ``workspace``; nothing is
uncommitted; every commit is on a remote branch; nothing in it changed in
the last ``idle_hours`` (by file times, because a new worktree's tip is an
old commit); and its branch's PR is merged or closed, or its tip is in the
base branch. A worktree with an open PR is never stale.

**Slots.** The ledger is a JSON file: each slot's name, model, agent, task,
whether the agent waits, and the tickets each model has failed. ``set``
refuses an occupied slot, ``remove`` an occupied one, ``add`` a model not in ``models``; a
refusal exits 2 and changes nothing. ``check --running NAME ...`` lists the
slots whose agent is not among the names (the session passes what its own
agent listing shows). ``next`` reads GitHub and prints one sorted list, each
line saying why it is where it is:

1. the author's fix for a review that asked for changes, on an unmoved head;
2. a review of a PR whose checks are all green on its head and which has no
   review of that head (the reviewer is never the author);
3. a new PR: an open ticket of the project or a library, with a priority
   label, not referenced by an open PR.

**Slot log.** The ledger keeps only the present, and a resumed agent
overwrites its own timestamps, so idle and waiting time could only be
estimated (dev-skill-up/pitboss#17). Every ``slots`` change therefore also
appends a JSON line to ``[slots] log`` for each slot whose state (running,
waiting or empty), agent or task now differs from its last line, or that is
new to the log or gone from the ledger (state ``removed``, which ends its
slot time). ``slots report CONFIG [--since T] [--until T]`` replays the log:
each line lasts until the slot's next line (or the window's end), is cut to
the window, and the seconds in each state are printed as shares, for each
slot and for all slots together.

Nothing predicts which files a ticket will touch (an earlier version held
back a ticket whose backticked paths an open PR changed; the owner dropped
that guess on 2026-10-22). Tickets are taken in strict order, every PR
starts from the base branch (no stacking), and a conflict is resolved by
merging the base branch in when it arises.

Inside a category, oldest first by the PR's (or the ticket's) creation
time; in the third, by ``priority_labels`` first. Each line names the
smallest model it may go to: the first of ``models`` that has not failed
the ticket and is no smaller than a ``model_labels`` label on it. Empty
slots are filled smallest model first, each with the first line it may take.

Output
------

Every line that calls for an action says the action. The markers
(``RUNNER PRESSURE``, ``STRAGGLER``, ``STALE WORKTREE``, ``EMPTY SLOT``, ``SLOTS FREE``,
...) are members of one enum, ``pitboss.markers.Marker``, printed as the
member's name in words (so ``READY_TO_MERGE`` prints ``READY TO MERGE``,
and the line with no pressure reads ``NO RUNNER PRESSURE``); a check in CI
fails when one is not explained in the skill's references, or the
references name one that does not exist. Timings go to stderr.

Code
----

The package follows the python-standard template's rules, checked with no
suppressions anywhere (no ``noqa``, ``type: ignore`` or ``pragma: no
cover``): classes are frozen dataclasses with no behaviour, and behaviour is
module functions over them. ``parsing`` turns GitHub's response bodies into
``shapes`` dataclasses, its wire strings into enums and booleans, so nothing
else reads JSON. ``ledger`` returns a ``Refusal`` rather than raising. Tests
inject a fake ``gh`` (canned bodies by path) and run real git in temporary
directories; ``unittest.mock`` is never used.

The skill
---------

The repository is also a Claude Code plugin marketplace laid out like
``dev-skill-up/ai-skills``: ``.claude-plugin/marketplace.json``,
``plugins/pitboss/.claude-plugin/plugin.json`` and
``plugins/pitboss/skills/sweep/``. The skill is named ``sweep`` (a skill
named ``steward`` or ``babysit`` changes how every PR-watching session
behaves). ``SKILL.md`` says when and how to run it; ``references/sweep.md``
explains every line and the runner-pressure hold; ``references/slots.md``
the ledger and the order of work; ``references/adversarial-review.md`` how
reviews are read and written. None of them names a project, a label or a
model.

The deterministic skill zips go to ``skill-zips/``, not ``dist/``, because
``dist/`` is where ``python -m build`` writes.
