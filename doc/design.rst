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
     - The report, in order: the project's PRs, the libraries'
       PRs, runner pressure, queue runs, stragglers, worktrees, disk
       pressure, the reminders, the slots. Exits 1 when a PR has a failed check or a
       merge conflict. It reads, except that under ``[clean] worktrees =
       "auto"`` (the default) it removes the finished worktrees that pass the
       safety test (see **Worktrees**), through ``args.safe_run``, with no
       dry run.
   * - ``pressure CONFIG``
     - Appends a look (``none`` or ``hold``) to the record and prints the
       runner-pressure line; exits 0 only after ``[runners] quiet_minutes``
       with no hold, else 1 with the minutes remaining.
   * - ``queued CONFIG``
     - Appends a hold to the record: a job was put on the queue (after a
       merge, an enqueue or auto-merge armed), so the quiet period restarts.
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
   * - ``lint pr-body|review|brief FILE [--head SHA] [--config CONFIG]``
     - The forms of the texts agents write (pitboss#37), one file each; the
       phrase check of ``lint text`` runs on the same file. Prints one
       finding per line ending with its check in parentheses, exits 1 on
       any, 0 on none (``ok``), 2 on a file or configuration it cannot use.
       ``pr-body``: ``first-line`` (``Fixes #N``), ``one-ticket``, ``head``
       (a ``Head: <40 hex>`` line, the last equal to ``--head``),
       ``evidence`` (an Evidence heading and a fenced block starting
       ``$ <command>``) and ``footer`` (only when ``[lint.pr_body] footers``
       lists lines: one of them in the last three lines; by default none is
       listed, so no footer is required). ``review``: the lines of ``[review.form]``
       (``first-line``, ``reviewed``, ``verdict``) and the reviewed SHA
       against ``--head`` (``head``); with ``--gated`` the lines of
       ``[review.gated_form]`` are read as a gate reads them, each once
       (``exact``), in plain ASCII (``plain``), with the full SHA.
       ``brief``: every ``[lint.brief] required`` line start begins a line
       (``required-line``), and with ``--ticket`` each line of the ticket's
       Done-when section is in the brief word for word (``done-when``).
       Without ``--config`` the generic forms of ``doc/example.toml`` are
       used.
   * - ``lint event EVENT STATUS [--url URL] [--config CONFIG]``
     - The ``text-lint`` commit status of a ``pull_request_target`` event
       (pitboss#38). Reads the pull request's body, head SHA, head branch and
       author from the event file EVENT, runs the checks of ``lint pr-body``
       (against the event's head), ``lint text`` and ``lint contradictions``
       on the body, prints every finding, and writes the JSON body of GitHub's
       create-a-commit-status call to STATUS: ``success`` with ``ok``,
       ``failure`` with the first finding as the description (ASCII, at most
       140 characters), or ``success`` with ``exempt`` for a head branch that
       starts with ``relock/`` and an author whose login ends with ``[bot]``.
       The status's ``target_url`` is ``--url``. Exits 0 once the file is
       written, 2 on an event or a file it cannot use. The reusable workflow
       ``.github/workflows/text-lint-check.yml`` runs it and posts the file
       with ``gh api``: it checks out pitboss at its ``tools-ref`` input (the
       caller repeats its own commit, as a reusable workflow cannot read its
       ref), never the pull request, and the body reaches pitboss only in the
       event's file. Callers are made from ``templates/text-lint.yml``, by
       commit, never ``@main``.
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
   * - ``slots show|set|free|add|remove|failed|check|next CONFIG ...``
     - The worker-slot ledger, and the sorted list of what to start next. Every
       one but ``report`` exits 1 with ``LEDGER MISSING`` and writes nothing when
       the ledger file does not exist (the owner creates it; only ``sweep`` starts
       one from the configured defaults). ``check`` takes ``--running NAME ...``
       and an optional number N: it exits 1 when the ledger has fewer than N rows.

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
at once in a thread pool. Only the latest run of each check name on the PR's
current head counts: a run of another head is dropped, and of two runs of one
name the one that started later (then the higher id) stands, so a cancelled
or superseded run never shows as failed. A line shows ``mergeable_state``, auto-merge,
pending checks, the failed checks with their job ids, the PR's place in the
merge queue (from the ``merge_group`` runs: ``queued``, ``in_progress``, or
the newest run's conclusion), and the review's standing. Action lines follow.
First ``STALL`` (``pitboss.stall``; a PR whose head branch starts with
``relock/`` and whose required check, named ``check`` or ``<caller> / check``, has
been red for more than 14400 seconds from the run's ``completed_at``, counted
against the injected clock: exactly 14400 is not yet one; the line says how long
and, for each failed check, the names of its failed steps; the skill's rules take
a stall before every other pull request but the merge of a ready one, unless the PR also has ``RULING DUE`` or ``PAUSE``), then
``UPDATE`` (``pitboss.updateline``; the PR is ``behind`` the base, at least one
check run of the head has completed and none is pending, and the repository is
not under ``[merge_queue] repositories``, whose queue builds each entry on the
current base), then ``RULING DUE`` or ``PAUSE`` (``pitboss.flow.next_step`` gives the step,
``pitboss.roundline`` prints; see **Review rounds** below), then
``WAIT-FOR-CI`` (no check run of the head has completed, draft or not: never
ready for review or to merge, though a draft's first review, Plan and
Execution, and the review of a revised plan are started by its author's
hand-back), ``CONFLICT``, ``FAILED`` (one line for each failed check, saying why from
api.github.com only: the names of the job's failed steps, the check run's
output title and summary, and its failure annotations, cut to 300 characters;
no job log is downloaded, because the log is a redirect to blob storage that a
sandbox may block), then ``READY TO MERGE`` (at least one check finished, all
finished and none failed, state ``clean``, an approving review of this head, or for an
ungated repository of an older head when everything since is merges of the
base branch) or, in a ``no_auto_merge`` repository, ``MERGE BY HAND``, or
else ``AUTO MERGE OFF`` for a PR with auto-merge off, not in the queue, nothing
failed, no conflict and not a draft, whose newest review approved this exact head
(``review=approved-this-head``; pitboss#85: with no review, a review of an older
head, one asking for changes or one standing ``plan-approved``, arming auto-merge
could merge a head nobody approved, so there is no line).

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
answered from what is recorded of the PR in a ``PullState`` (its body, labels,
comments, reviews as ``Graded`` and checks): ``is_paused_for_owner``,
``newest_counting_review``, ``has_plan_execution_body``, ``is_draft``,
``can_undraft``, ``plan_approved``, ``get_plan_rejections``, ``opus_used``,
``execution_fixed_since_plan_approval``, ``ci_result`` and ``has_conflict``.
The steps are in ``pitboss.steps`` and what follows an Opus ruling is
``pitboss.rulings.after_opus_ruling``. Only comments by trusted authors count,
read with the reader of the repository's review form (strict where gated); a
ruling is a comment whose first line is exactly ``Opus ruling``. ``pitboss next
CONFIG TICKET`` scans the open PRs of the configuration once, picks the PR whose
body says ``Fixes`` the ticket and prints its step, and for a ticket no PR fixes
the first step. The sweep's ``RULING DUE``, ``PAUSE``, ``revise the plan``,
``fix the review`` and ``review it`` lines and ``slots next`` take that step.
GitHub's own reviews have no ``Plan:`` line and count in no plan rejection. A PR
with either marker is offered for no fix, update or review round in ``slots
next``, and its ticket stays taken.

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
PRESSURE`` line and the removal of worktrees (``worktrees.py``) all call it. So a
finished worktree is kept when anything in it changed in the last ``idle_hours``
(by file times, because a new worktree's tip is an old commit), when it holds a
``.pitboss-live`` marker or is a live path, when it is a link or holds a mount
point, when it is or holds the directory the command runs in (``PWD`` or the
process's own), when a commit in it is on no remote branch, or when a tracked
file in it is changed (untracked files are scratch to the test). A finished
worktree that passes the test but holds untracked files is kept too, with their
count, because ``git worktree remove`` refuses it without ``--force``, which
pitboss never passes. A worktree on no branch or on the base branch is finished
when its tip is in the base branch, unlike a checkout of **Dead paths**, so a
persistent one carries ``.pitboss-live``. ``[clean] worktrees`` chooses what a
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
depth or in a directory above it, a path of ``[clean] live``, the main clone, or
one that holds or lies in such a path), when it is a symbolic link, when it is
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
then names the five largest safe dead paths; it scans for them only then.

**Slots.** The ledger is a JSON file: each slot's name, model, agent, task,
whether the agent waits, and the tickets each model has failed. ``set``
refuses an occupied slot, ``remove`` an occupied one, ``add`` a model not in ``models``; a
refusal exits 2 and changes nothing. ``check --running NAME ...`` lists the
slots whose agent is not among the names (the session passes what its own
agent listing shows). ``next`` reads GitHub and prints one sorted list, each
line saying why it is where it is. The open PRs that need a fix of a review, an
update or a review come first, in one list ordered oldest first, whatever each
needs; each line says which of the four kinds it is, and a PR is listed once,
as the first of these kinds that fits:

* ``revise the plan``: a review that asked for changes on an unmoved head
  graded the plan changes needed (keyword: plan-revision, pitboss#82); the
  author edits the ``## Plan`` section of the body and touches no code, doc or
  test until the plan is approved, and the review of the revised plan grades
  the plan alone;
* ``fix the review``: the author's fix for a review that asked for changes, on
  an unmoved head, that did not reject the plan;
* ``update``: a PR whose ``mergeable_state`` is ``behind`` and whose checks
  have all finished (a behind PR whose checks still run is not listed; one in
  a repository under ``[merge_queue] repositories`` is never an update).
  ``pitboss sweep`` prints it as an ``UPDATE`` line;
* ``review it``: a review of a PR whose checks are all green on its head and
  which has no review of that head, or only one that approved the plan alone
  (the reviewer is never the author).

A PR with ``RULING DUE`` or ``PAUSE`` (above) is listed as none of the four.
After them come the new PRs, ordered by ``priority_labels`` first and then
oldest first: an open ticket of the project or a library, with a priority
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

The open PRs are ordered oldest first by creation time, and the tickets by
``priority_labels`` first and then oldest first by creation time (the one
exception is a ``STALL`` line of the sweep, whose fix the skill's rules take
before every line of this list; a PR with ``RULING DUE`` or ``PAUSE`` has no line
in it). Each line names the
smallest model it may go to: the first of ``models`` that has not failed
the ticket and is no smaller than a ``model_labels`` label on it. Empty
slots are filled smallest model first, each with the first line it may take.

Output
------

Every line that calls for an action says the action. The markers
(``RUNNER PRESSURE``, ``STRAGGLER``, ``STALE WORKTREE``, ``DISK PRESSURE``, ``EMPTY SLOT``, ``SLOTS FREE``,
``RULING DUE``, ``PAUSE``, ``NO HAND-BACK``, ...) are members of one enum, ``pitboss.markers.Marker``, printed as the
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

The skill divides the reading of a pull request (pitboss#83). The orchestrator
dispatches a new reviewer when the sweep shows a review is due, and reads no
body, diff or evidence first; its only reads of a pull request are the sweep's
markers and the review's verdict line. The reviewer checks the ``Head:`` line,
that the Evidence is real output on the head, and the checks, and its brief
names those three checks.

The deterministic skill zips go to ``skill-zips/``, not ``dist/``, because
``dist/`` is where ``python -m build`` writes.
