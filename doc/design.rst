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
   * - a repository with ``.github/workflows/review-gate.yml`` needs the form
       that file accepts
     - read from the file on the default branch (``gates.py``; keyword:
       review-gate): such a repository is gated, in the file's first line,
       ``Verdict:`` line and ``Reviewed:`` line, whatever ``[review]
       gated_form`` says; ``review-form`` prints it, the reviewer brief quotes
       it, and the sweep prints ``GATE PENDING`` while the status
       ``adversarial-review`` of the head is not success
   * - an approval survives a merge of main, except in gated repositories
     - built in: it is what "gated" means
   * - the 20 shared runners, and which repositories share them
     - ``[runners] repositories`` (default: the project and its libraries)
   * - the working files outside any repository (sweep configurations, the
       ledger and log, the pressure record, notes) are lost with the container
     - ``[sync]``: ``pitboss sync`` copies them to ``directory`` of
       ``repository``'s main (default ``moshez/claude-jsonl``,
       ``notes-current``), and a sweep does it last
   * - a queue run's 60 minute limit
     - ``[merge_queue] timeout_minutes``
   * - quire has a merge queue, so a PR that is behind needs no update
     - ``[merge_queue] repositories`` (default none: a behind PR with finished
       checks is an update)
   * - three hours of idleness before a finished worktree may be removed
     - ``[worktrees] idle_hours`` (it is the idleness of a scratch entry too)
   * - ``/tmp/claude-0``, shared caches, the 5 GiB of free space
     - ``[clean] scratch``, ``[clean] live``, ``[clean] min_free_gib``
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
   * - "stop opening new quire pull requests until the existing ones are
       finished" (the owner, 2026-10-30)
     - ``[holds] new_pull_requests`` (repositories, default none) and
       ``max_open`` (default 0: hold while more than that many of the
       repository's PRs are open). ``slots next`` prints its tickets as
       ``HELD`` and offers none; the sweep prints one ``HOLD`` line
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
  The order of the tickets, which come after the open PRs, is
  ``priority_labels``; nothing in the code or the references names a label.
* ``slots check`` was to list agents "the session no longer runs". Only the
  session can see its agents (``ListAgents``; subagents share one process,
  so ``ps`` cannot count them), so the session passes the names it sees:
  ``slots check CONFIG --running NAME ...``.

Nothing else in the code is a choice: the merge-queue branch shape
(``gh-readonly-queue/<base>/pr-<n>-<sha>``), the check-run conclusions that
count as failed (``failure``, ``timed_out``, ``action_required``,
``startup_failure``; a ``cancelled``, ``skipped`` or ``neutral`` run is not
one, since a concurrency group cancels the run it supersedes; a failed run is
also not one when a passing commit status posted after it completed is the
same check's: the status context is the run's name, or the status's
``target_url`` names the run or another run of the same workflow file, since
a job ``lint`` posts the status ``text-lint``), the dequeue reasons and
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
     - The report, in order: the project's PRs, the libraries'
       PRs, runner pressure, queue runs, stragglers, worktrees, disk
       pressure, the reminders, the slots. Exits 1 when a PR has a failed check or a
       merge conflict. It reads, except that under ``[clean] worktrees =
       "auto"`` (the default) it removes the finished worktrees that pass the
       safety test (see **Worktrees**), through ``args.safe_run``, with no
       dry run, and, in the same mode, closes the open PRs of the ``[scratch]``
       repositories whose workflow runs finished and deletes their branches
       (keyword: scratch, pitboss#142; a kept fixture is never touched; in
       ``"list"`` mode it prints ``SCRATCH PR`` for them).
   * - ``pressure CONFIG``
     - Appends a look (``none`` or ``hold``) to the record and prints the
       runner-pressure line; exits 0 only after ``[runners] quiet_minutes``
       with no hold, else 1 with the minutes remaining.
   * - ``queued CONFIG``
     - Appends a hold to the record: a job was put on the queue (after a
       merge, an enqueue or auto-merge armed), so the quiet period restarts.
   * - ``ruling-summary CONFIG``
     - Appends the time to ``.git/pitboss-ruling-summaries.log`` of the main
       clone: the daily summary of the Opus rulings was written (pitboss#237,
       keyword: ruling-summary). The Pacific day (``America/Los_Angeles``) of
       a recorded time ends the sweep's ``OPUS RULINGS DAILY`` line for that
       day.
   * - ``push CONFIG [--draft] [--no-dry-run] [GIT_ARGUMENTS]``
     - The pressure check, then ``git push``; a push that goes out appends a
       hold, a refused or failed one appends nothing. ``--draft`` skips both.
       Dry run unless ``--no-dry-run``; put ``--`` before git's options.
   * - ``cancel-stale-runs CONFIG``
     - Cancels the queue runs that are not the newest of their PR. Dry run
       unless ``--no-dry-run``.
   * - ``clean-worktrees CONFIG``
     - Removes the finished worktrees that pass the safety test, then
       ``git worktree prune``; branches are kept. Prints ``REMOVED WORKTREE``
       or ``KEPT WORKTREE`` for each. Dry run unless ``--no-dry-run``.
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
   * - ``lint text FILE... [--phrases FILE]...``
     - Banned phrases (pitboss#35). Prints one finding per line (file, line,
       label, the line, the phrase, what to do instead), exits 1 on any,
       0 on none, 2 on a file or phrase file it cannot use. The phrase file
       pitboss ships (``phrases.tsv``) is always used; each ``--phrases`` adds
       a project's file (``--no-default-phrases`` leaves the shipped one out).
       A phrase file has a line for each phrase: label, pattern, example,
       what to do instead, tab separated, ``#`` lines skipped. The pattern
       is a character, ``\s \d \w \b``, ``\<c>``, a class, and ``? + *``
       on one atom, searched without regard to case; a group or an
       alternation is refused (an alternative is a line of its own), and an
       example that its pattern does not match is refused.
   * - ``lint contradictions FILE... [--pairs FILE]...``
     - A rule stated two ways (pitboss#36). Prints two lines for each pair
       whose two sides the files hold (one line for each side, naming the
       other's place and what to do instead), exits 1 on any, 0 on none, 2
       on a file or pairs file it cannot use. The pairs pitboss ships
       (``contradictions.tsv``: who owns CI until it is green, what a pull
       request reports about what CI runs, the priority order, provenance of
       the owner's rules, who deletes the persistent checkout) are always
       used; each ``--pairs`` adds a project's file (``--no-default-pairs``
       leaves the shipped one out). A pairs line is two patterns of the
       phrase language, an example of each and what to do instead, tab
       separated; the text between backticks is not searched.
   * - ``lint pr-body|review|brief|owner-card FILE [--head SHA] [--branch BRANCH] [--config CONFIG] [--plan-approved] [--ruling URL FILE]... [--comments FILE]``
     - The forms of the texts agents write (pitboss#37), one file each; the
       phrase check of ``lint text`` runs on the same file. Prints one
       finding per line ending with its check in parentheses, exits 1 on
       any, 0 on none (``ok``), 2 on a file or configuration it cannot use.
       ``pr-body``: ``first-line`` (``Fixes #N``), ``one-ticket`` (``Fixes`` or
       ``Closes`` lines for more than one ticket, unless the body cites the
       address of an Opus ruling comment of the PR whose ruling is ``do these
       steps``; the comments come from ``--ruling URL FILE`` (repeatable: a
       comment's address and the file holding its text) and from ``--comments
       FILE`` (the API's list of the PR's comments, all its pages, of which
       the ``Opus ruling`` comments of the ``[review] trusted_associations``
       count; a file that is not there is no comments); ``lint event`` takes
       the same two, so the ``text-lint`` status of a PR with a cited ruling
       is success; ``pitboss next`` and the blockers read a ``Closes #N``
       line as a ticket the PR fixes; the sweep prints ``FOLDED PR`` for an
       open PR that cites no such ruling; pitboss#171), ``head``
       (a ``Head: <40 hex>`` line, the last equal to ``--head``),
       ``evidence`` (an Evidence heading and, in its section, a block that
       ``pitboss expand`` produced), ``hand-typed`` (a ``$ `` row anywhere in
       the body, in a quote, a list or an indented block too, that is not
       inside a block ``pitboss expand`` produced, one finding for each,
       naming its line), ``appended`` (an Evidence row, in a block ``pitboss
       expand`` produced, whose command ends in ``; echo $?``, ``&& echo $?``
       or ``|| echo``: ``expand`` prints ``exit status: N`` itself, so the row
       was changed from the Plan's command; pitboss#170, one finding for each,
       naming its line), ``test-name`` (only with ``--checkout DIR``, the
       head's checkout: every ``test_...`` identifier in the Plan and
       Execution sections needs a ``def`` of it, or a module of that name, in
       the tree of ``DIR``; one finding for each identifier it lacks, naming
       it; pitboss#189), ``plan-command`` (each ``$ `` command of the Plan
       section needs a block ``pitboss expand`` produced in the Evidence
       section whose command is the same string, or the same string with a
       cut or a pipe after it, not ``||``; one finding for each command that
       has none, ``plan command not run as written: line N COMMAND: run it as
       written; the only reasons to run another are that it is impossible or
       dangerous, and then stop, show the output that proves it, and change
       the Plan and have it reviewed first (plan-command)``; pitboss#196) and
       ``footer`` (only when ``[lint.pr_body] footers``
       lists lines: one of them in the last three lines; by default none is
       listed, so no footer is required). With ``--branch`` starting with the
       ``[relock] prefix`` (default ``relock/``; pitboss#126) the PR is a relock
       PR, which fixes no ticket and has no Plan, Execution or hand-run
       evidence: only ``head``, ``hand-typed`` and ``footer`` are checked, and
       ``plan-command`` is not (``relock_pr_body`` does not call it).
       ``review``: the lines of ``[review.form]``
       (``first-line``, ``reviewed``, ``verdict``) and the reviewed SHA
       against ``--head`` (``head``); with ``--gated`` the lines of
       ``[review.gated_form]`` are read as a gate reads them, each once
       (``exact``), in plain ASCII (``plain``), with the full SHA. With
       ``--gated --repository NAME`` the form is the one ``review-form`` prints
       for that repository (its ``review-gate.yml`` read through the default
       branch, else the configured form), not ``[review.gated_form]``, which
       may differ from the gate's.
       ``brief``: every ``[lint.brief] required`` line start begins a line
       (``required-line``), and with ``--ticket`` each line of the ticket's
       Done-when section is in the brief word for word (``done-when``).
       ``owner-card`` (pitboss#168, keyword: how-we-got-here): the text of an
       owner decision card, its question and reason, has a line that starts
       with the words ``How we got here`` and an analysis after them
       (``how-we-got-here``; ``pitboss.analysis``).
       Without ``--config`` the generic forms of ``doc/example.toml`` are
       used.
   * - ``lint event EVENT STATUS [--url URL] [--config CONFIG] [--ruling URL FILE]... [--comments FILE]``
     - The ``text-lint`` commit status of a ``pull_request_target`` event
       (pitboss#38). Reads the pull request's body, head SHA, head branch and
       author from the event file EVENT, runs the checks of ``lint pr-body``
       (against the event's head, with the PR's ruling comments from
       ``--comments``, so a body that closes several tickets and cites an Opus
       ruling comment of ``do these steps`` is in form; pitboss#171),
       ``lint text`` and ``lint contradictions`` on the body, prints every finding, and writes the JSON body of GitHub's
       create-a-commit-status call to STATUS: ``success`` with ``ok``,
       ``failure`` with the first finding as the description (ASCII, at most
       140 characters), or ``success`` with ``exempt`` for a head branch that
       starts with ``relock/`` and an author whose login ends with ``[bot]``.
       The status's ``target_url`` is ``--url``. Exits 0 once the file is
       written, 2 on an event or a file it cannot use. The reusable workflow
       ``.github/workflows/text-lint-check.yml`` fetches the PR's comments
       with ``gh api`` into the file ``--comments`` reads (a caller grants
       ``pull-requests: read`` in the same change that moves its pin to this
       commit: GitHub lets a called workflow keep or lower the caller's
       ``GITHUB_TOKEN`` permissions, never raise them, so a caller without it
       fails at startup and posts no status; a caller on an older pin is
       unaffected), runs it and posts the file with ``gh api``: it checks out pitboss at its ``tools-ref`` input (the
       caller repeats its own commit, as a reusable workflow cannot read its
       ref), never the pull request, and the body reaches pitboss only in the
       event's file. Callers are made from ``templates/text-lint.yml``, by
       commit, never ``@main``.
   * - ``clean CONFIG [--dry-run]``
     - The cleaning a sweep does first, on its own (keyword: auto-clean,
       pitboss#120; see **Automatic cleaning** below): removes at once, with no
       dry run unless ``--dry-run``. The answer to a denied ``rm``. It also
       closes the finished scratch PRs (see ``sweep``); ``--dry-run`` lists them.
   * - ``nox [-- MODULE...]``
     - The worker's local check (keyword: nox-runner, pitboss#210; see
       **The local check** below). Runs ``nox -r -s`` for ``tests-3.13``,
       ``skills``, ``lint`` and ``mypy``, in that order, and stops at the
       first that fails: exit 1 with that session's output. Words after ``--``
       are test modules, passed to the tests session only. Prints one line for
       each session that ran (name, ``success`` or ``failed``, seconds) and, on
       success, that CI's ``Run Nox`` step is the proof of the whole suite.
       Runs no other session: docs, dry_release and the other Python versions
       are CI's.
   * - ``expand TEMPLATE [--cwd DIR] [--pr OWNER/NAME#N [--limit N] [--no-dry-run]]``
     - A PR body whose evidence is produced, never typed (pitboss#117; see
       **Expanding a template** below). Without ``--pr``
       prints TEMPLATE with each directive run in DIR (default: the current
       directory). Exits 0 whatever the
       commands' statuses, 2 on a template or directory it cannot use (and
       prints nothing: every directive is read before any runs). With
       ``--pr`` it prints the description it set: that body, or, for a body
       over ``--limit`` (default 65536), its first part with the citations of
       the later parts, which are posted as comments (keyword: expand-split,
       pitboss#177; see **Expanding a template**);
       a dry run unless ``--no-dry-run``; 2 on a ``--pr`` that is not
       ``OWNER/NAME#NUMBER`` or a limit the body cannot be cut to.
   * - ``clean-container CONFIG [--approved FILE] [--batch N]``
     - Lists, and with ``--no-dry-run`` removes, the dead paths (keyword:
       clean-container, pitboss#7; see **Dead paths** below). Also the
       regular files directly in ``--root`` (default ``/``) modified more than
       ``--hours`` (default 1) after ``--marker`` (default
       ``/container_info.json``, the one file a Claude Code on the web
       container starts with there; none when it is absent); subdirectories,
       symbolic links and other entries there are left alone. A root file
       obeys the same liveness, idle and safety rules as any dead path.
   * - ``review-form CONFIG REPOSITORY``
     - Prints the form a review comment in that repository must take.
   * - ``plan-check FILE``
     - Runs each command of the ``## Plan`` section of the PR body saved in the file, in a scratch worktree, before the Plan is reviewed (pitboss#192). The orchestrator runs it on a PR at ``PLAN_CHECK`` (the Plan has commands and no trusted PR comment records a clean check of this Plan) and posts the whole output as a PR comment: the first line ``Plan check``, a row for each command, the ``Plan digest:`` line and the last line ``Plan check: ok`` or ``Plan check: refused``. Exit 1 when a row did not run, 2 for a body it cannot read. The Plan review is offered only after a trusted comment says ``Plan check: ok`` for the digest of the Plan now in the body.
   * - ``slots show|set|free|add|remove|failed|check|next|report|time CONFIG ...``
     - The worker-slot ledger, and the sorted list of what to start next. Every
       one but ``report`` and ``time`` exits 1 with ``LEDGER MISSING`` and writes nothing when
       the ledger file does not exist (the owner creates it; only ``sweep`` starts
       one from the configured defaults). ``set`` takes ``--kind`` (``start``,
       ``review``, ``fix`` or ``ruling``), records the ticket the task works on
       and is refused when the ticket cannot be named; a ``set`` with the same
       agent and ``--kind fix`` resumes the running agent as an entry. ``check`` takes ``--running NAME ...``
       and an optional number N: it exits 1 when the ledger has fewer than N rows.
       ``free`` prints the ledger, then the ``EMPTY SLOT`` line that ``next``
       gives the freed slot (one function, ``nextview.refill_line``), or
       ``no task is waiting``. ``next``, ``free`` and ``set`` exit 1 with
       ``not the orchestrator config: use PATH`` and leave the ledger alone
       when the configuration does not own it (``[slots] ledger-owner = true``,
       or the ledger's ``"config"`` key is the configuration's path;
       ``ledgerowner.owner``); a sweep of such a configuration starts with
       ``NOT THE ORCHESTRATOR CONFIG``.

Reads go through gather's ``args.safe_run``; every change on GitHub or to
git (cancelling a run, removing a worktree) goes through ``args.run``, so it
happens only with ``--no-dry-run``. Two things are not so: ``slots`` writes its
own ledger, and ``sweep`` under ``[clean] worktrees = "auto"`` removes worktrees
through ``args.safe_run``, since it takes no ``--no-dry-run``.

Every command first reads each configured repository once; one the session
cannot read is reported as ``UNREADABLE`` and left out, so one missing grant
does not stop a sweep. Only the project's own repository is required. A PR
one of whose API calls fails is reported the same way
(``UNREADABLE owner/name#7: check-runs answered HTTP 500``) and the sweep
goes on with the others. So is a merge-queue run whose jobs call fails
(``UNREADABLE owner/name#7: jobs answered HTTP 500``): it is left out of the
runner count and the pressure line holds, never ``NO RUNNER PRESSURE``, since
a count that is incomplete cannot tell a free runner (``pressure`` and
``push`` refuse instead). While any PR is unreadable no ticket is offered as new
work (``UNREADABLE tickets: not offered as new work``), because that PR may
already work on it. A trusted comment with a ``Verdict:``, ``Plan:`` or
``Execution:`` line whose first line is not the repository's review first line
is no review to the sweep, so it is named, not read as no review
(``UNREADABLE REVIEW owner/name#7: <comment URL> is not in the review form:
...``); the reviewer is asked to post it again in the form.

How each part decides
---------------------

**Pull requests.** One request for the PR list, then, per PR, its details,
its comments and reviews, and one request for its head's check runs, all PRs
at once in a thread pool. Only when one of those runs has failed (the latest
run of its name) are two more reads made: the head's commit statuses (the
newest of each context) and, for a status that does not carry the check's
name, the workflow file of the Actions run of the status and of the check
(``actions/runs/<id>``). Only the latest run of each check name on the PR's
current head counts: a run of another head is dropped, and of two runs of one
name the one that started later (then the higher id) stands, so a cancelled
or superseded run never shows as failed. A failed run is also not failed
(``pitboss.supersede``) when a passing commit status posted after it
completed is the check's: the status context is the run's name, or the run
its ``target_url`` names is the check's run or a run of the same workflow
file (a job ``lint`` posts the context ``text-lint``); a status that is
older, or not ``success``, leaves the failure, so the newest of the two
decides. A line shows ``mergeable_state``, auto-merge,
pending checks, the failed checks with their job ids, the PR's place in the
merge queue (from the ``merge_group`` runs: ``queued``, ``in_progress``, or
the newest run's conclusion), and the review's standing. Action lines follow.
First ``STALL`` (``pitboss.stall``; a PR whose head branch starts with
the relock prefix (``relock/`` by default) and whose required check, named ``check`` or ``<caller> / check``, has
been red for more than 14400 seconds from the run's ``completed_at``, counted
against the injected clock: exactly 14400 is not yet one; the line says how long
and, for each failed check, the names of its failed steps; the skill's rules take
a stall before every other pull request but the merge of a ready one, unless the PR also has ``RULING DUE``, ``RULING UNREADABLE``, ``RULING ESCALATES``, ``PAUSE`` or ``PLAN EDITED``), then
``UPDATE`` (``pitboss.updateline``; the PR is ``behind`` the base, at least one
check run of the head has completed and none is pending, and the repository is
not under ``[merge_queue] repositories``, whose queue builds each entry on the
current base), then ``RULING DUE``, ``RULING UNREADABLE``, ``RULING ESCALATES``, ``PAUSE`` or ``PLAN EDITED`` (``pitboss.flow.next_step`` gives the step,
``pitboss.roundline`` and ``pitboss.planeditline`` print; see **Review rounds** below), then
``WAIT-FOR-CI`` (no check run of the head has completed, draft or not: never
ready for review or to merge, though a draft's first review, Plan and
Execution, and the review of a revised plan are started by its author's
hand-back; a draft at a round has ``DRAFT ROUND`` instead, ``pitboss.report``, the
same words as ``slots next``, pitboss#156; a draft whose Plan is approved, with
a diff that touches ``e2e/`` or a ``[sweep] run_by_e2e`` prefix and no completed
``workflow_dispatch`` run of ``check.yml`` at its head (a draft's own run skipped e2e, complete
or not; one still running is waited for), has ``RUN E2E BEFORE APPROVAL: dispatch check.yml on <branch>``
instead when nothing is running at its head (while a check run of the head is unfinished it is ``waiting for CI at this head``), pitboss#199), ``CONFLICT``, ``FAILED`` (one line for each failed check, saying why from
api.github.com only: the names of the job's failed steps, the check run's
output title and summary, and its failure annotations, cut to 300 characters;
no job log is downloaded, because the log is a redirect to blob storage that a
sandbox may block), then ``READY TO MERGE`` (at least one check finished, all
finished and none failed, state ``clean``, in a gated repository the head's
``adversarial-review`` status is success (else ``GATE PENDING``), an approving review of this head, or for an
ungated repository of an older head when everything since is merges of the
base branch, or the flow's step is the merge because the newest readable Opus
ruling says ``execution is approved`` and no review follows it) or, in a
``no_auto_merge`` repository, ``MERGE BY HAND``, or
else ``AUTO MERGE OFF`` for a PR with auto-merge off, not in the queue, nothing
failed, no conflict and not a draft, whose newest review approved this exact head
(``review=approved-this-head``; pitboss#85: with no review, a review of an older
head, one asking for changes, one standing ``plan-approved`` or
``older-body``, arming auto-merge could merge a head nobody approved, so there
is no line; a head the Opus ruling
approved gets ``READY TO MERGE`` instead).

**Body fixes** (pitboss#147). A review may record the PR body it read in a
``Body: <digest>`` line (``pitboss body-digest FILE``, and ``pitboss plan-digest FILE`` for the ``Plan digest:`` line of the Plan section; REST has no edit time
for a body). When the newest review of the head records a digest other than the
body's now, the standing is ``older-body``, the review does not count in
``flow.newest_counting_review``, and ``slots next`` offers the PR as ``review
the fix round's findings only``, unless the review rejected the Plan: then as
``review it`` with the Plan alone graded (pitboss#167). A review with no such line is keyed to the
head alone.

**Reviews.** A review is the newest comment by a trusted author whose lines
match the repository's form. In a gated repository the form is strict: the
first line is exactly the first template line, each template line matches
exactly one line, and the comment is ASCII with no code fence, HTML or link
definition. A GitHub review (``APPROVED`` or ``CHANGES_REQUESTED`` on a
``commit_id``) by a trusted author counts too, except in a gated
repository, where only the comment form does. For an ungated repository an
approval of an older head carries over when the commits since are all
merges (the non-merge commits of ``base...head`` are those of
``base...reviewed``). A newer trusted comment whose first line says review and
a verdict but is not in the form (``Independent re-review``) is not a review;
the PR's line says so (``review=... (ignored: the comment of <time> is not in
the review form)``), so the older review is not taken for the last word
unseen (#20). A review comment also carries what its ``Plan:`` line grades and
whether it has an ``Execution:`` line (keyword: plan-revision, pitboss#82). A
head whose newest review asks for changes and grades the plan changes needed
stands ``plan-changes-needed``; one whose newest review approves and has a
``Plan: approved`` line but no ``Execution:`` line (a review of a revised plan,
which grades the plan alone) stands ``plan-approved``, is no approval to merge,
is not carried over merges of the base, and gets no ``AUTO MERGE OFF`` line
(auto-merge is never armed on it, as on any head without an approving review). Both words are on the PR's line.

**Review flow** (keyword: review-flow, pitboss#107). The step a PR is at is one
function, ``pitboss.flow.next_step``, the owner's pseudo code branch for branch
(the lint cuts it at its own section comments, each ending in a call to the
next). Every question it asks is a function of its own in ``pitboss.flow``,
answered from what is recorded of the PR in a ``PullState`` (``pitboss.flowstate``; its body, labels,
comments, reviews as ``Graded`` and checks): ``is_paused_for_owner``,
``newest_counting_review``, ``is_draft``,
``can_undraft``, ``plan_approved``, ``get_plan_rejections``,
``newest_ruling``, ``readable_ruling``,
``execution_fixed_since_plan_approval``, ``ci_result`` and ``has_conflict``.
``execution_fixed_since_plan_approval`` is the count of the execution (keyword:
ruling-count, pitboss#149): an execution rejection on the approved plan is
followed by a fix round when the head moved by more than merge commits or the
body is no longer the one that review recorded (``bodydigest``), and the next
rejection is then ``OPUS_RULING``.
The steps are in ``pitboss.steps``; what follows an Opus ruling is the table
``pitboss.flowstate.AFTER`` (``pitboss.rulings.after_opus_ruling`` follows it too).
Only comments by trusted authors count,
read with the reader of the repository's review form (strict where gated); a
ruling is a comment whose first line is exactly ``Opus ruling`` and whose second
line is ``Ruling: <word>`` (``pitboss.rulingwords.Ruling``); the newest such
comment decides. One that cannot be read is the step ``FIX_RULING`` (checked
right after the pause label, so a draft gets it too), never a pause. A rejection
pauses (``PAUSE_FOR_OWNER``) only when its review was posted after a readable
ruling; a readable ruling that no review follows gives its own first step from
the table (the later steps are not wired: a worker's push moves the head and the
ordinary review gate takes over), ``RULING_ESCALATES`` for ``escalate to the
owner`` and the merge (or the conflict's resolution) for ``execution is
approved``. ``pitboss next
CONFIG TICKET`` scans the open PRs of the configuration once, picks the PR whose
body says ``Fixes`` or ``Closes`` the ticket and prints its step, and for a ticket no PR fixes
the first step. A ruling comment without a ``How we got here`` section (an
analysis of each rejection before the ruling: ``pitboss.analysis``, pitboss#168)
is read and followed all the same; the sweep says so with ``RULING NO ANALYSIS``
(``pitboss.analysisline``). The sweep prints one ``OPUS RULINGS DAILY`` line
(``pitboss.summaryline``, ``pitboss.rulingsummary``, pitboss#237, #239) after the slots when a trusted Opus
ruling comment of an open, merged or closed PR or of an issue (read from each
repository's ``issues/comments`` since the last summary) is dated after the
last recorded summary and none is recorded for the Pacific day; the orchestrator writes the summary of every
Opus ruling of the day, each with a suggested mitigation, as a markdown
artifact and records it with ``ruling-summary``. The ``RULING ESCALATES`` and
``PAUSE`` lines and steps say the owner's card carries a markdown artifact with
the sections ``What happened``, ``Recommendation`` and ``Suggested
mitigation`` (``pitboss.steps.OWNER_ARTIFACT``). The sweep's ``RULING DUE``, ``PAUSE``, ``RULING UNREADABLE``,
``RULING ESCALATES``, ``PLAN EDITED``, ``revise the plan``,
``fix the review`` and ``review it`` lines and ``slots next`` take that step.
GitHub's own reviews are no regular review and count nowhere in the flow. A PR
at ``OPUS_RULING``, ``PAUSE_FOR_OWNER``, ``FIX_RULING``, ``RULING_ESCALATES``, ``PLAN_EDITED`` or ``PLAN_CHECK`` is
offered for no fix or review round in ``slots next``, and its ticket stays taken. A draft whose Plan
is not approved, and a PR with no review, is at ``PLAN_CHECK`` while its Plan has commands and no trusted
PR comment records a clean ``pitboss plan-check`` of it; the orchestrator runs that command and posts its output as a PR comment (pitboss#192).

**Findings in one round** (keyword: all-findings, pitboss#169). The brief of a
review of a stage (the Plan, the Execution, or both) requires the first round of
that stage to read the whole PR body, the whole diff and every command of the
Plan against the repository and to list every finding in that one review; a Plan
review also tries each Plan command as a read-only dry run where it can be tried
and reports each that cannot run as written. A later round on the same stage
checks the earlier findings and the findings the changes since caused; a finding
it raises that is present in the unchanged text of an earlier head is written on
a line of its own that starts with ``Missed earlier:``. ``pitboss.missed`` counts
those lines in each regular review, and the sweep's ``PAUSE`` line says how many
the reviews before and after the newest Opus ruling hold, for the analysis of why
a PR still needs changes after a ruling. The brief of the review after a fix round
(``review the fix round's findings only``) names the diff since the reviewed head
(``git diff <reviewed head>..<head>``) and the earlier findings; the reviewer may
raise nothing outside them, and when every finding is fixed as asked and the fixes
do not invalidate the approved Plan the verdict is approved and the PR is
mergeable.

**tracefs.** ``sweep``, ``pressure`` and every ``slots`` action first make
the mount themselves (keyword: tracefs, pitboss#28): ``grep tracefs
/proc/mounts``, else ``mount -t tracefs nodev /sys/kernel/tracing``, and say
one line on stderr: ``tracefs: found mounted``, ``tracefs: mounted`` or
``tracefs: NOT MOUNTED (mount exit status N)``. Stdout and the exit status of
the command are not changed. The tool makes the mount, not the environment's
setup script: that script runs only for a new session, not after a container
restart, and no agent can see whether it ran. Where there is no
``/proc/mounts`` (macOS, the BSDs) the check fails like an unmounted tracefs,
the mount is tried and its failure is the line (127 when ``grep`` or ``mount``
is not installed); the command goes on. The mount runs in a dry run too.

**Runner pressure.** Under pressure when any ``merge_group`` run, queued or
in progress, in any ``[runners] repositories``, has a job still ``queued``.

**Quiet period** (keyword: quiet-period, pitboss#66, from quire#905). A hold
lifts only after ``[runners] quiet_minutes`` (default 15) with no hold, because
some jobs take a minute to trigger in a serial queue, and a job put on the
queue is pressure at once, so stuffing the queue cannot eject entries (a
dequeued entry restarts the merge queue and causes endless holds). The record
(``[runners] record``, default ``pitboss-pressure.log`` in the main clone's
``.git``) has a line ``<ISO time with offset> none|hold`` for each ``pressure``
look and each queued job. The quiet period runs from the newest hold, or from
the oldest line when there is no hold; it is over when that is at least
``quiet_minutes`` ago (exactly that is over), and the look being made counts:
a look that sees a job waiting is a hold. Robustness: a missing or empty record
has seen no quiet yet (the first look starts it); a line that cannot be read
(not two fields, a time without an offset, a word other than ``none`` and
``hold``, bytes that are not UTF-8) is taken as a hold at the time of the next
good line, or of the look being made when it is the last, so it never makes a
quiet period that was not seen and ages out; a last line cut short is not
glued to the next; a record that cannot be read or written stops the command.
``push`` records only a push that went out; if that record write fails it says
the push went out and exits 2 (git's own status when git fails, 1 when refused).
``sweep`` reads the record without writing it and prints the same line, so its
``NO RUNNER PRESSURE`` means the quiet period is over; a record it cannot
read is its own ``RUNNER PRESSURE`` line (a hold) and the sweep goes on.

**Queue runs.** The unfinished ``merge_group`` runs of every repository
read; a run is stale when its merge group (its ``gh-readonly-queue`` branch)
is not its PR's newest. Runs of the newest group are never stale, one per
workflow. A live run is reported with its age against ``timeout_minutes``.

**Stragglers.** Every git checkout directly under ``workspace``: uncommitted
files, and commits on no remote branch. Each repository is fetched once.

**Worktrees** (keyword: clean-worktrees, pitboss#81). A worktree of
``main_clone`` is *finished* when it is not the main clone, is under
``workspace``, and its branch's PR is merged or closed, or (with no PR) its tip
is in the base branch (``local.finished_reason``); a worktree with an open PR
never is. Whether a finished worktree may go is the one safety test of **Dead
paths** (``dead.verdict``): not live, not in use, and safe. It is written once:
``clean-container`` (``dead.consider`` and ``dead.recheck``), the ``DISK
PRESSURE`` line and the removal of worktrees (``worktrees.py``) all call it; the
two differences are that, under disk pressure, ``worktrees.py`` passes
``dead.Look.unmarked`` so a merged worktree's own marker is not honored, except
on the one whose PR merged last (``judging.last_merged``), and that, at any disk
level, a merged worktree's marker older than a worker's task, 6 hours
(``workhours.TASK_HOURS``, pitboss#194), is not honored either. The 6 hours
have no source in the ticket (#194 says "the worker's task bound" and #185,
which it cites, sets none) or in the repository before: the value is the
orchestrator's choice in pitboss#194, and the constant defines the bound. So a
finished worktree is kept when anything in it changed in the last ``idle_hours``
(by file times, because a new worktree's tip is an old commit), when it holds a
``.pitboss-live`` marker or is a live path (a merged worktree's own marker is
not honored under disk pressure, except on the one whose PR merged last, nor at
any disk level once it is older than 6 hours),
when it is a link or holds a mount
point, when it is or holds the directory the command runs in (``PWD`` or the
process's own), when a commit in it is on no remote branch, or when a tracked
file in it is changed (untracked files are scratch to the test). A finished
worktree that passes the test but holds untracked files is kept too, with their
count, because ``git worktree remove`` refuses it; pitboss passes ``--force``
only to remove a worktree whose ``.pitboss-live`` marker it ignored, under disk
pressure or for its age of over 6 hours (``worktrees.removal_line``), where the
marker is the only untracked file. A worktree on no branch or on the base branch
is finished when its tip is in the base branch, unlike a checkout of **Dead
paths**, so a persistent one carries ``.pitboss-live`` (under disk pressure that
keeps a merged one only when its work merged last, and a marker older than 6
hours keeps a merged one at no disk level). ``[clean] worktrees`` chooses what a
sweep does with the finished worktrees: ``auto`` (the default) removes each that
passes, one at a time, judging it right before its ``git worktree remove``,
and prints ``REMOVED WORKTREE <dir> (<reason>)`` or, for one that fails,
``KEPT WORKTREE <dir> (<why>)``, then runs ``git worktree prune`` and prints a
line with the count removed, the space freed (the sizes ``survey`` measured) and
the count kept; ``list`` removes nothing and prints ``STALE WORKTREE`` for each
that passes, and ``clean-worktrees`` removes those. ``clean-worktrees`` always
removes, whatever the key says, and prints the same lines (with "dry run" and
"would be freed" unless ``--no-dry-run``). A worktree git refuses to remove (a
locked one) is ``COULD NOT REMOVE WORKTREE``. Research: ``git clean -n`` lists
before it removes and ``systemd-tmpfiles`` removes by age with exclusions (the
comparison of **Dead paths**), and a sweep that only listed left twenty stale
worktrees on disk for hours while the disk filled (pitboss#81).

**Automatic cleaning** (keyword: auto-clean, pitboss#120). The owner, 2026-10-31:
"Pitboss sweep should *automatically* be cleaning things that can be cleaned, and
we can enable more aggressive cleaning if the disk is over 90%. Better to delete
something that someone needed than to halt and wait for me" and "NEVER ASK ME
AGAIN". The disk had filled with about 2,750 ``/tmp/tmpXXXXXXXX`` directories
from worker test runs, a fix round stopped, and the orchestrator asked before
deleting. So cleaning is a command (``autoclean.clean_lines``, called first by
``sweep`` and on its own by ``clean``), not a step an agent decides, and it has
no prompt and no dry-run default. Research: ``systemd-tmpfiles`` removes by age
with exclusions (the tmp.conf ``D``/``q`` lines age out ``/tmp`` after 10 days,
``/var/tmp`` after 30), ``tmpreaper`` and ``tmpwatch`` are the same by atime or
mtime, and the kubelet's image and container garbage collection has a low
threshold that cleans the oldest unused first and a high one (85%, 80%) that
cleans down to a target; here the one switch is the file system's use, 90% by
default, as the owner said. A normal run removes (1) the finished worktrees and
the dead checkouts, judged by the one safety test (``dead.verdict``; a linked
worktree with untracked files is left to its own section, since git keeps it,
except under pressure, or at any disk level once a merged worktree's marker is
older than 6 hours, one whose only untracked file is an ignored
``.pitboss-live`` marker, which that section removes with ``--force``);
(2) the test tempdirs of ``[clean] tmp_roots`` (default ``/tmp``) whose name
matches ``tmp_patterns`` (default ``tmp????????``, ``tmp.??????????``,
``pytest-of-*``, ``pip-*``), owned by the user running (``os.getuid``), not a
link, not marked ``.pitboss-live``, with no mount point in it, not the
directory the command runs in or above it, and with nothing in it changed for
``tmp_hours`` (default 24). At or over ``pressure_percent`` (default 90) of the
used space of any file system of the workspace, a tempdir root or a scratch
directory the run is aggressive: tempdirs of ``pressure_tmp_hours`` (default 1),
every worktree whose branch has no open PR (``Reason.NO_OPEN_PR``) and every
checkout of a repository with no open PR (``Reason.QUIET_REPOSITORY``), and the
package caches that regenerate (``~/.cache/pip``, ``~/.cache/uv``,
``~/.cache/pre-commit``, ``~/.npm/_cacache``, ``~/.cargo/registry/cache`` and
``[clean] caches``). Under pressure a merged worktree's own ``.pitboss-live``
marker is not honored, except on the worktree whose work merged last
(``judging.last_merged``, by ``mergetime``): each other one is removed, with
``--force`` when the marker is its only untracked file, and prints ``REMOVED
WORKTREE <dir> (<reason>; its .pitboss-live marker is ignored: a worktree merged
after it)``, and the last one prints ``KEPT WORKTREE <dir> (holds a file named
.pitboss-live; its PR merged last)`` (pitboss#185). At any disk level, normal
or aggressive, the marker of a merged worktree or checkout (or one whose tip is
in the base branch) is not honored once it is older than 6 hours (``workhours.TASK_HOURS``; the bound is the
orchestrator's choice in pitboss#194, see **Worktrees**), even on the one whose
work merged last: it is removed, with ``--force`` as above, and prints
``REMOVED WORKTREE <dir> (<reason>; its .pitboss-live marker is older than 6
hours, longer than a worker runs)``. A marker of a worktree with an open PR, of
a closed unmerged one, or of a scratch or tempdir path, is honored whatever its
age. It
never touches, in either mode, a worktree with an open PR, a running worker's
directory (anything changed within ``idle_hours``, or marked ``.pitboss-live``;
the marker of a merged worktree is ignored under pressure, except the one whose
PR merged last, and at any disk level once it is older than 6 hours), the main
clone, a live path or the directory it runs in, and it says so (``clean: never
touched``, and under pressure ``clean: kept <path> (open PR)`` for each such
worktree). A commit on no remote branch and a
changed tracked file still keep a worktree (the safety test is one): losing
that is not "something someone needed" but work that exists nowhere else.
Every directory of the workspace that holds a git checkout and is not a
registered worktree of the main clone, a full clone of a repository the
configuration does not name included, is judged by the PRs of its own
``origin`` (``deadscan.dead_checkouts``; a clone is a checkout whose ``.git`` is
a directory, so ``git worktree list`` never showed it, pitboss#194): under
pressure it is removed when its branch has no open PR, and a checkout that is
kept, because its branch has an open PR, git cannot read it, it has no
``origin`` or its repository's PRs could not be read, or that is live or in
use, is named with the reason (``clean: kept <path> (<why>)``, one line for
each directory of the workspace that is not a registered worktree, which says
itself why it is kept; a directory that is not a git checkout is kept as ``not
a git checkout``). Under pressure the sweep also says what it freed and what it
could not (``account.py``): ``clean: freed by kind: worktrees <size>, checkouts <size>, test tempdirs
<size>, package caches <size>`` ("would be freed" in a dry run) and, when the
sum is less than what the crowded file systems need to get under
``pressure_percent``, a shortfall line (``clean: <size> freed, <size> short of
the <size> needed to get under 90%: each directory over 500 MB that was kept``)
and, for each kept directory over 500 MB, largest first, ``clean: kept <size>
<path> (<why>): over 500 MB``. Under
``[clean] worktrees = "list"`` a normal run only lists the worktrees and leaves
the checkouts; pressure overrides it. The output is the mode line, a
``REMOVED``/``COULD NOT REMOVE`` line for each path, ``clean: N paths removed,
X freed; disk free A before, B after``, and under pressure the lines of the
account above. The disk reader (the parser's ``args.usage``, also read by the
``DISK PRESSURE`` line), the clock, the
user id, the home directory and the file system are injected
(``autoclean.Machine``, ``autoclean.Filesystem``), so the tests play the ages,
the 90% switch, the never-touch list and the report on a fake.

**The local check** (keyword: nox-runner, pitboss#210). The full ``nox -r``
takes about seven minutes and CI's ``Run Nox`` step runs it on every push, so a
worker running it only duplicates CI (the workers of #166 and #167 spent about
half their time on it). ``pitboss nox`` is the one command that does the right
thing: the tests of one Python version first (until they run there is no reason
to lint the code), then the ``skills`` session, ``lint`` and ``mypy``, each with
``-r``, stopping at the first failure; ``pitboss nox --
pitboss.tests.test_gates`` runs only those test modules. The worker briefs tell
the worker to run it after each edit and never the full ``nox -r``, never to
run ``virtue`` by hand, to start nothing in the background that needs polling
(one foreground command under ``timeout 598``, or one ``Monitor`` with an
``until`` loop), and that throwing away a first design is acceptable
(pitboss#175). The Plan never names it or any nox run as its evidence
(pitboss#179): the suite is CI's. The Plan brief, the Plan review brief and the
worker brief carry the CI pointer rule (pitboss#179): a Plan row whose result a
CI run shows asks for no long local command and points to CI by workflow, step,
a greppable string and the run for the head, the Plan review rejects a row that
does not, and the PR body holds evidence only for what CI does not show. The worker briefs
say that a lint, check or exemption that is new or loosened ships a test for the
nearest input it must still reject, and the full and the Execution review briefs
make one without it changes needed (pitboss#180). The ruling brief says that a
ticket or ruling that changes the order in which steps are offered gives, in its
Done-when, a table of the full order and a test per row, and the full, Plan and
Execution review briefs make a doc row or the code that differs from that table
changes needed (pitboss#182). The sweep prints ``POLLING`` for a running
worker with over 40 tool calls whose last 20 are ``Monitor`` calls or ``sleep``
commands (keyword: polling), read from the transcripts in ``[slots]
transcripts``, matching the slot's agent to the ``name`` in the transcript's
``.meta.json``.
The runner and the clock are injected (``noxcheck.Runner``, ``noxcheck.Clock``),
so the tests play the order, the stop and the flags on a fake.

**Expanding a template** (keyword: expand, pitboss#117). Workers typed
evidence from inference and got it wrong (a count of five for six commits, a
mutation run described in prose, a block that dropped a line of output). The
worker writes a template and ``pitboss expand`` runs it, so the body's
evidence is only ever a command and what it printed.

*Syntax.* A line of the template that starts with ``$ `` (a dollar sign and a
space, at the start of the line) is a directive: the rest of the line is a
command line for ``sh -c``. Every other line is kept as it is; a line that
starts with ``\$ `` is kept as ``$ `` and is not run. A directive is one line
(a longer command is a committed script the line calls) and has a command.
There are no other directives and nothing built in: the head is
``$ git rev-parse HEAD``, a count of commits is
``$ git log origin/main..HEAD --oneline | wc -l`` and a file is
``$ cat < path``. Each directive becomes a fenced block: the opening line is
the fence, ``pitboss-expand`` and ``sha256=`` followed by 16 hex digits of the
SHA-256 of the stored form of the lines inside (no BOM, no carriage return, a
URL the store wrapped in double backticks unwrapped; keyword: store-form,
pitboss#164); inside are ``$ `` and the command exactly as
written, the output as it came with a BOM and carriage returns removed
(standard output and standard error
together, invalid UTF-8 bytes as backslash escapes, no other trimming or
filter),
a line ``\ No newline at end of output`` when the output ends without a
newline, and ``exit status: N`` when the status is not zero. The fence is
longer than any run of backticks inside. ``expand`` exits 0 whatever the
statuses (a red run is evidence too); a template it cannot read, a directive
with no command or a missing ``--cwd`` is exit 2 before any command runs.

*A body over the store's limit* (keyword: expand-split, pitboss#177). A PR
body over 65536 characters breaks and loses its footer, and workers posted
evidence in comments by hand. ``--pr OWNER/NAME#N`` cuts the expanded body
into parts on paragraph markers: a blank line outside a fence, or the closing
fence of a block ``expand`` produced; a block is cut only when it alone is
longer than a part (then at line ends, and a line longer than a part inside
the line), and such a block is refused by ``lint pr-body`` as edited. Part 1
stays the description, with the closing paragraph (when it holds no block and
is under a quarter of the limit: the footer) after a section ``## Evidence in
comments`` that cites each later part's comment URL and each row in it. Parts
2 and on are comments that start with ``<!-- pitboss-expand-part N of M -->``.
A rerun rewrites those comments in order (the URLs stay), adds comments for
more parts and removes the ones a shorter body does not need; comments that do
not start with the marker are never touched. The description, the comments
and their URLs come from deterministic code, never from the worker.

*Mutation runs.* A run that edits, runs and restores is a script committed in
the PR (for example ``scripts/mutate.sh``, restoring with ``git checkout``
or ``trap``), and a directive calls it: ``$ sh scripts/mutate.sh src/a.py``.
The reviewer reads the script in the diff and the output under the command, so
neither is described in prose.

*The mark.* ``lint pr-body`` refuses rather than parses containers. A
command row is a line that, after any ``>``, list markers (``-``, ``+``, ``*``,
``1.``, ``1)``), spaces and tabs, starts with ``$`` and a space, a tab or the
end of the line. It is accepted only inside a fenced block whose opening line
is the mark with the digest of the block's own contents; every other command
row, anywhere in the body, is ``hand-typed``: a row in a fence inside a quote
or a list, an indented row, ``$`` and a tab, a row of a four-space code block,
and a row under a heading lint cannot see (a setext heading is a heading on
GitHub). A block produced by ``expand`` elsewhere in the body is fine. Fences
follow CommonMark: an opening fence is indented at most 3 spaces, a closing
fence is indented at most 3 spaces, holds only fence characters and is at
least as long as the opening one, so a line indented 4 spaces or by a tab does
not close a block. The ``evidence`` check and this one share one definition of
the section: an ATX heading (one to six ``#``, a space or a tab, up to 3
spaces of indentation) whose title starts with Evidence, to the next heading of
the same or a higher level, fences respected; ``evidence`` requires a produced
block inside it (a row the Plan points to CI needs none: the Plan holds its
pointer, pitboss#179). A block edited after ``expand`` (one changed character breaks
the digest) is refused. The digest is not a secret: it detects a block that
is typed or edited by mistake, and a person who computes it has gone round the rule on purpose.

*Trust boundary.* The commands run with ``sh -c`` in ``--cwd`` with the
permissions and environment of whoever runs ``pitboss expand``: no sandbox, no
filtering. A template is therefore the worker's own file in the worker's own
checkout, and ``expand`` is never run on a template taken from a pull
request's text, a comment, or a branch that is not the worker's (for a
workflow, never on ``pull_request_target``). ``lint`` only reads text and runs
nothing.

*Research.* knitr runs the code of a chunk (a fence with ``{r}`` and options)
and writes the output under it, prefixing each line (``##`` by default) and
carrying on after an error by default; we keep the idea that the document runs
its own commands but prefix nothing, since the output has to stay raw.
cog (``[[[cog`` ... ``]]]`` with the generated text up to ``[[[end]]]``) and
mdsh (a block ``$`` command, re-run in place, ``--frozen`` to fail in CI)
mark generated text with markers; we mark with the fence's opening line so
that the lint can tell the generated from the typed, and put a digest in it so
an edit is seen. embedme (``<!-- embedme path -->``) and rustdoc doctests
(``no_run``, ``should_panic`` as attributes of the fence) put the directive in
the fence or a comment; we use a bare ``$`` prompt line, the form a reader already
knows from a terminal and the form the existing Evidence check looks for, so a
template reads like the body it makes. None of the five has a way to say
"edit, run, restore": each calls out to a program, as ours does.

**Dead paths** (keyword: clean-container, pitboss#7). The comparable tools
decide the same way: systemd-tmpfiles removes by age and has entries that
exclude a path (``x``, ``X``), ``git clean -n`` lists before it removes, and the kubelet evicts on a free-space threshold of
the filesystem (``nodefs.available<10%``). A path is *dead* when its work is
finished or nobody uses it, and *live* when it is marked; a dead path is *safe*
when nothing in it exists only on this machine. Sources of dead paths:
``dead_checkouts`` (git checkouts directly under ``workspace``: the branch's
newest PR in the checkout's own repository merged or closed, found from the
common git directory of ``main_clone`` or from ``remote.origin.url``, else the
tip is in the base branch with no PR; a checkout on the base branch, on no
branch, or whose repository could not be fetched is not judged), ``dead_scratch``
(entries of ``[clean] scratch`` directories that are not symbolic links) and
the root files above; the pressure scan lists the same three sources. A path
is skipped, never listed, when it is live (a file ``.pitboss-live`` in it at any
depth or in a directory above it, except that for a merged checkout a marker
older than 6 hours, ``workhours.TASK_HOURS``, is not honored, which
``clean-container`` passes as ``marker_expiry``; a path of ``[clean] live``, the
main clone, or one that holds or lies in such a path), when it is a symbolic link, when it is
or holds the directory the command runs in (``PWD`` or the process's own, so a
sweep never removes the worktree it runs from), or when
anything in it changed in the last ``idle_hours`` (by file times, in the whole-tree
walk below; this also holds for the root files; ``.git`` contents do not count, as a fetch
changes them). One whole-tree walk (``survey``) measures a path and finds, at
any depth, its git checkouts, bare repositories, live markers and mount points.
It never follows a link (a link counts as itself, so a link to a big directory
adds nothing) and does not enter a mount point, which is named. A dead path is
safe when each git checkout in it has every commit on a remote branch and no
changed tracked file. A standalone clone counts every ref (other local
branches and the stash included, ``rev-list --all --not --remotes=origin``); a
linked worktree, or a repository outside the path, counts its HEAD only; a
repository whose git directory is inside the path (a submodule) goes with it.
Else it is kept, with the reason, and never removed: a commit or change that
exists only here, a checkout git cannot read, a bare repository, a mount point
inside, or a path that cannot be looked at. Sizes are the blocks on disk.
``--no-dry-run`` removes at most ``--batch`` paths at a time with ``rm -rf
--one-file-system`` and, just before each part, looks at every path again
(liveness, idle, safety): a path that became live, busy or unsafe in between is
left in place and reported as ``COULD NOT REMOVE PATH``. Only paths directly
inside the workspace, a ``[clean] scratch`` directory or ``--root`` can be
removed; the ``[clean]`` paths must be absolute. It then prunes the worktree
lists of the repositories a removed linked worktree belonged to. ``--approved
FILE`` limits the removal to the paths in it; an entry that is not among the
current safe candidates is refused, whatever it is. The sweep warns with
``DISK PRESSURE`` when the free space of a filesystem of ``workspace`` or of a
scratch directory is under ``[clean] min_free_gib`` (default 5; 0 never) and
then names the five largest safe dead paths; it scans for them only then. The free space comes from the same injected reader
(``args.usage``), so a test gives the figure.

**Slots.** The ledger is a JSON file: each slot's name, model, agent, task,
ticket, kind, whether the agent waits, and the tickets each model has failed. ``set``
refuses an occupied slot, except a ``--kind fix`` set with the same agent (a fix round that resumes it), ``remove`` an occupied one, ``add`` a model not in ``models``; a
refusal exits 2 and changes nothing. ``check --running NAME ...`` lists the
slots whose agent is not among the names (the session passes what its own
agent listing shows). ``next`` reads GitHub and prints one sorted list, each
line saying why it is where it is. The open PRs that the flow's step gives a
round come first, in one list ordered oldest first, whatever each needs; each
line says which kind it is, the kind being the flow's step alone
(``pitboss next`` prints the same step). A PR has exactly one step, so it is
listed at most once. The eight kinds:

* ``revise the plan``: step ``WORKER``, task ``REVISE_PLAN`` (keyword:
  plan-revision, pitboss#82); the author edits the ``## Plan`` section of the
  body and touches no code, doc or test until the plan is approved, and the
  review of the revised plan grades the plan alone;
* ``fix the review``: step ``WORKER``, any other task (``FIX_EXECUTION``): the
  author's fix for a review that asked for changes to the execution;
* ``fix the CI``: step ``WORKER``, task ``FIX_CI``: a red CI, which is no
  rejection, unless the PR waits for a ruling or the owner (``steps.WAITS``,
  pitboss#183);
* ``write the Plan and Execution body``: step ``WORKER``, task
  ``FIRST_ROUND``: the PR has no such body;
* ``resolve the conflict``: step ``WORKER``, task ``RESOLVE_CONFLICT``: an
  head that conflicts with the base, at any stage but while the PR waits for
  a ruling, the owner or the restoring of an edited approved Plan
  (``steps.WAITS``, ``PLAN_EDITED`` included, the ``paused-owner`` label and
  ``RULING UNREADABLE``);
* ``do the ruling's steps``: step ``WORKER``, task ``RULING_STEPS``: the
  newest readable Opus ruling says ``do these steps`` and no review follows it;
* ``carry out the ruling``: step ``WORKER``, task ``RULING_AS_GIVEN``: the
  ruling says ``split``, ``reshape`` or ``abandon`` (``revise the plan`` is
  ``revise the plan`` above);
* ``review it``: step ``REGULAR_REVIEW``, the reviewer never the author. On a
  PR that is not a draft it comes once every required check finished green on
  the head; it is the plan-only review when the newest review rejected the Plan
  and no review names this head or body (pitboss#167). On a draft it is the
  plan-only review, listed with no CI, since a draft runs none, before every
  new ticket (pitboss#156); a draft is undrafted only once its Plan is approved
  and no review at its head asks for changes (that fix comes first, pitboss#176).

A PR with ``RULING DUE``, ``RULING UNREADABLE``, ``RULING ESCALATES``, ``PAUSE`` or ``PLAN EDITED`` (above) is listed as none of these.
After them come the new PRs, ordered by ``priority_labels`` first and then
oldest first: an open ticket of the project or a library, with a priority
label, not referenced by an open PR, except a ticket of a repository under
the owner's hold (``[holds] new_pull_requests``; keyword: pr-hold), which is
printed as ``HELD`` and offered to no slot. A ticket that is blocked in the
form of ``rules.md``, "A blocked ticket is not started", while the ticket or PR
it names is open is printed as
``BLOCKED <ticket> by <owner/repo#n>`` by ``slots next`` and the sweep and is
offered to no slot (keyword: ticket-blocked, ``pitboss.ticketblock``); it is
listed again when the blocker closes or merges.

**Slot log.** The ledger keeps only the present, and a resumed agent
overwrites its own timestamps, so idle and waiting time could only be
estimated (dev-skill-up/pitboss#17). Every ``slots`` change therefore also
appends a JSON line to ``[slots] log`` for each slot whose state (running,
waiting or empty), agent, task, ticket or kind now differs from its last line,
for every ``slots set`` even when it equals the last line (a ``begun`` entry,
as a fix round that resumes the agent), or that is
new to the log or gone from the ledger (state ``removed``, which ends its
slot time). ``slots report CONFIG [--since T] [--until T]`` replays the log:
each line lasts until the slot's next line (or the window's end), is cut to
the window, and the seconds in each state are printed as shares, for each
slot and for all slots together. ``slots time CONFIG [--since T] [--until T]``
replays it too: the worker minutes (running, not waiting) of each ticket, the
count of ``set`` entries behind each total, and the median and mean over tickets.

Nothing predicts which files a ticket will touch (an earlier version held
back a ticket whose backticked paths an open PR changed; the owner dropped
that guess on 2026-10-22). Tickets are taken in strict order, every PR
starts from the base branch (no stacking), and a conflict is resolved by
merging the base branch in when it arises.

The open PRs are ordered oldest first by creation time, and the tickets by
``priority_labels`` first and then oldest first by creation time (the one
exception is a ``STALL`` line of the sweep, whose fix the skill's rules take
before every line of this list; a PR with ``RULING DUE``, ``RULING UNREADABLE``, ``RULING ESCALATES``, ``PAUSE`` or ``PLAN EDITED`` has no line
in it). Each line names the
smallest model it may go to: the first of ``models`` that has not failed
the ticket and is no smaller than a ``model_labels`` label on it. Empty
slots are filled smallest model first, each with the first line it may take.

Output
------

Every line that calls for an action says the action. The markers
(``RUNNER PRESSURE``, ``STRAGGLER``, ``STALE WORKTREE``, ``DISK PRESSURE``, ``EMPTY SLOT``, ``SLOTS FREE``, ``HOLD``, ``HELD``,
``RULING DUE``, ``PAUSE``, ``NO HAND-BACK``, ...) are members of one enum, ``pitboss.markers.Marker``, printed as the
member's name in words (so ``READY_TO_MERGE`` prints ``READY TO MERGE``,
and the line with no pressure reads ``NO RUNNER PRESSURE``); a check in CI
fails when one is not explained in the skill's references, or the
references name one that does not exist. Timings go to stderr: each section
of a sweep ends with a line ``[pitboss Ns] <section>: <seconds>s, <count>
commands`` and the kinds of command it ran, and a section over 30 seconds
names the commands it waited longest for (``pitboss.timing``,
``pitboss.calllog``). The reads of a section that are alike (the repositories,
the PRs, the checkouts) are made at once (``pitboss.concurrently``), and a PR
is read once for the whole sweep.

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

The skill divides the reading of a pull request (pitboss#83). The orchestrator
dispatches a new reviewer when the sweep shows a review is due, and reads no
body, diff or evidence first; its only reads of a pull request are the sweep's
markers and the review's verdict line. The reviewer checks the ``Head:`` line,
that the Evidence is real output on the head (a row the Plan points to CI has
the pointer instead), and the checks, and its brief
names those three checks.

The deterministic skill zips go to ``skill-zips/``, not ``dist/``, because
``dist/`` is where ``python -m build`` writes.
