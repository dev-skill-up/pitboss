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
       per clone, never committed)
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
count as failed (``failure``, ``cancelled``, ``timed_out``,
``action_required``, ``startup_failure``), the dequeue reasons and
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
   * - ``review-form CONFIG REPOSITORY``
     - Prints the form a review comment in that repository must take.
   * - ``slots show|set|free|add|remove|failed|check|next CONFIG ...``
     - The worker-slot ledger, and the sorted list of what to start next.

Reads go through gather's ``args.safe_run``; every change on GitHub or to
git (cancelling a run, removing a worktree) goes through ``args.run``, so it
happens only with ``--no-dry-run``. ``slots`` writes its own ledger.

How each part decides
---------------------

**Pull requests.** One request for the PR list, one per PR for its details
and one for its head's check runs, all PRs at once in a thread pool. A line
shows ``mergeable_state``, auto-merge, pending checks, the failed checks
with their job ids, the PR's place in the merge queue (from the
``merge_group`` runs: ``queued``, ``running``, or the last run's
conclusion), and for a library PR the review state and ``READY-TO-MERGE``
(checks all finished and none failed, state ``clean``, and an approving
review of this head; for an ungated repository also of an older head when
everything since is merges of the base branch). A library in
``no_auto_merge`` is marked so the reader merges it by hand.

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

**Queue runs.** The unfinished ``merge_group`` runs of the project; a run
that is not the newest of its PR is stale. A run is reported with its age
against ``timeout_minutes``.

**Stragglers.** Every git checkout directly under ``workspace``: uncommitted
files, and commits on no remote branch. Each repository is fetched once.

**Worktrees.** A worktree of ``main_clone`` is stale when all of these
hold: it is not the main clone and is under ``workspace``; nothing is
uncommitted; every commit is on a remote branch; nothing in it changed in
the last ``idle_hours`` (by file times, because a new worktree's tip is an
old commit); and its branch's PR is merged or closed, or its tip is in the
base branch. A worktree with an open PR is never stale.

**Slots.** The ledger is a JSON file: each slot's name, model, agent and
task, and the tickets each model has failed. ``set`` refuses an occupied
slot. ``next`` reads GitHub and prints one sorted list, each line saying
why it is where it is:

1. the author's fix for a review that asked for changes, on an unmoved head;
2. a review of a PR whose checks are all green on its head and which has no
   review of that head (the reviewer is never the author);
3. a new PR: an open ticket of the project or a library, with a priority
   label, not referenced by an open PR and naming no file an open PR
   changes.

Inside a category, oldest first by the PR's (or the ticket's) creation
time; in the third, by ``priority_labels`` first. Each line names the
smallest model it may go to: the first of ``models`` that has not failed
the ticket and is no smaller than a ``model_labels`` label on it.

Output
------

Every line that calls for an action says the action. The markers
(``RUNNER PRESSURE``, ``STRAGGLER``, ``STALE WORKTREE``, ``EMPTY SLOT``,
...) are members of one enum, ``pitboss.markers.Marker``; a check in CI
fails when one is not explained in the skill's references, or the
references name one that does not exist. Timings go to stderr.

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
