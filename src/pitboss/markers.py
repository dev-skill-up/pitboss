"""The markers that start the output lines a reader acts on.

A marker's text is its name in words, so the output and the references
spell it the same way; CI checks that the references explain every one, except
the ``SELF_EXPLAINED`` ones, whose line says what to do (no line is added to a
reference, pitboss#343).
"""

import enum


class Marker(enum.Enum):
    """A marker at the start of an output line that calls for an action.

    Attributes:
        OUTDATED: the running pitboss is older than PyPI's newest release.
        UNREADABLE: a repository the session cannot read, or a PR one of
            whose API calls failed.
        RUNNER_PRESSURE: queue runs wait for runners; hold.
        NO_RUNNER_PRESSURE: nothing waits for a runner.
        RUN_E2E_BEFORE_APPROVAL: a draft whose Plan is approved and whose diff
            touches what the e2e suite runs on, with no completed dispatched
            run at its head (its own run skipped e2e): dispatch the check
            workflow on its branch.
        FOLDED_PR: an open PR whose body closes several tickets and cites no
            Opus ruling that allows it.
        UPDATE: a PR is behind the base with every check finished.
        OPUS_RULINGS_DAILY: Opus ruling comments are dated since the last
            summary and none is recorded for the Pacific day.
        QUEUE_RUN: an unfinished queue run, with its age.
        STALE_QUEUE_RUN: a queue run of a superseded group.
        CANCELLED_STALE_QUEUE_RUN: one cancelled.
        COULD_NOT_CANCEL_STALE_QUEUE_RUN: one that could not be.
        STRAGGLER: work that exists only on this machine.
        ORPHANED_CHECKOUT: a directory whose git directory is gone.
        STALE_WORKTREE: a finished worktree still on disk.
        REMOVED_WORKTREE: one removed.
        KEPT_WORKTREE: a finished worktree that is not removed, and why.
        COULD_NOT_REMOVE_WORKTREE: one that could not be.
        DISK_PRESSURE: free space is under the configured minimum.
        DISK: the free space of the workspace's volume, in ``next`` and
            ``slots next`` (keyword: disk-watch, pitboss#288).
        REMOVED_PATH: a dead path removed by ``clean-container`` (or, in a dry
            run, one that would be).
        KEPT_PATH: a dead path that is not safe to remove.
        COULD_NOT_REMOVE_PATH: a path that is still there, or is not a safe
            dead path.
        SCRATCH_PR: an open PR of a scratch repository that is not a kept fixture: its
            run finished, or its head branch is not a run branch.
        CLOSED_SCRATCH_PR: a scratch PR closed (or, in a dry run, one that would
            be).
        DELETED_SCRATCH_BRANCH: the head branch of a closed scratch PR deleted.
        COULD_NOT_CLOSE_SCRATCH_PR: a scratch PR that could not be closed.
        COULD_NOT_DELETE_SCRATCH_BRANCH: a branch of a closed scratch PR that
            is not deleted, and why.
        SWEEP_REMINDER: a line each sweep ends with: the two fixed sentences
            (the owner's words, a worker's actions; pitboss#352), then the
            project's questions.
        EMPTY_SLOT: a worker slot with no agent.
        SLOTS_FREE: slots are free and work is queued; a wake-up is required.
        SLOT_IDLE: a slot empty for over two minutes (by the slot log) while
            work is queued.
        IDLE_SLOT: a slot free for over ten minutes with no agent dispatched
            for it, and the ``slots next`` line to dispatch (keyword:
            free-check, pitboss#450).
        CHECK_IN_OVERDUE: the last status post of the orchestrator is over
            thirty minutes old (keyword: check-in, pitboss#450).
        GONE_AGENT: a slot whose agent is no longer running.
        CHECK_BEFORE_YOU_ANSWER: the ledger is kept by hand; check it.
        WATCH_SLOT_FREE: ``slots watch`` found a free slot: the first startable
            item and its brief command, repeated each poll until it is filled.
        LEDGER_CHANGED: ``slots watch`` wrote the ledger (an agent began or ended).
        WATCH_MISSING: the sweep found no ``slots watch`` running: the Monitor
            invocation that starts it.
        PULL_NEEDS: an open PR is red or behind the base: what it needs (merge the
            base, fix the CI, re-dispatch the relock), not a review.
        NO_AGENT_RUNNING: the task list has no running agent: the slot is free.
        NEXT: a line of the sorted list of work.
        SUGGESTION: one of the top suggestions of ``next`` and ``slots next``,
            with the brief to paste.
        NO_HAND_BACK: an agent started over ten minutes ago that has said nothing.
        POLLING: a running worker with over 40 tool calls whose last 20 are
            ``Monitor`` calls or ``sleep`` commands.
        SYNCED: a working file copied to the sync repository's main.
        SYNC_SOURCE_MISSING: a file the sync is told to keep is not there.
        SYNC_NOT_CONFIGURED: the configuration has no ``[sync]`` table.
        NOT_SYNCED: a working file beside the configuration, or named by it, that
            ``[sync] paths`` does not keep.
        COULD_NOT_SYNC: git failed to bring the sync repository up to date or
            to push to it.
        NOT_THE_ORCHESTRATOR_CONFIG: the first line of a sweep of a configuration
            that does not own the slot ledger.
        INCOMPLETE: the last line of a sweep that could not read a configured
            repository, or the list of the owner's repositories (keyword:
            repo-access); the exit status is 1.
        STALE_CLAIM: a PR's body names a head that is not its head, so a worker's
            claim of a push was not true (keyword: claim-readback, quire#1115).
        ADOPT_REVIEW: a PR's body says the ``adopt`` script made it, so its review is
            of the script, not of the diff (keyword: adopt-made, pitboss#423).
        MECHANICAL_FIX: a PR's red is a failed plan job or a fixture expectation
            mismatch, which one push fixes and a push to a draft-free hold may
            exempt (keyword: mechanical-fix, pitboss#32).
        SLOW_MECHANICAL_FIX: a mechanical red whose fix push has not happened within
            the configured minutes.
    """

    OUTDATED = enum.auto()
    UNREADABLE = enum.auto()
    RUNNER_PRESSURE = enum.auto()
    NO_RUNNER_PRESSURE = enum.auto()
    RUN_E2E_BEFORE_APPROVAL = enum.auto()
    FOLDED_PR = enum.auto()
    UPDATE = enum.auto()
    OPUS_RULINGS_DAILY = enum.auto()
    QUEUE_RUN = enum.auto()
    STALE_QUEUE_RUN = enum.auto()
    CANCELLED_STALE_QUEUE_RUN = enum.auto()
    COULD_NOT_CANCEL_STALE_QUEUE_RUN = enum.auto()
    STRAGGLER = enum.auto()
    ORPHANED_CHECKOUT = enum.auto()
    STALE_WORKTREE = enum.auto()
    REMOVED_WORKTREE = enum.auto()
    KEPT_WORKTREE = enum.auto()
    COULD_NOT_REMOVE_WORKTREE = enum.auto()
    DISK_PRESSURE = enum.auto()
    DISK = enum.auto()
    REMOVED_PATH = enum.auto()
    KEPT_PATH = enum.auto()
    COULD_NOT_REMOVE_PATH = enum.auto()
    SCRATCH_PR = enum.auto()
    CLOSED_SCRATCH_PR = enum.auto()
    DELETED_SCRATCH_BRANCH = enum.auto()
    COULD_NOT_CLOSE_SCRATCH_PR = enum.auto()
    COULD_NOT_DELETE_SCRATCH_BRANCH = enum.auto()
    SWEEP_REMINDER = enum.auto()
    EMPTY_SLOT = enum.auto()
    SLOTS_FREE = enum.auto()
    SLOT_IDLE = enum.auto()
    IDLE_SLOT = enum.auto()
    CHECK_IN_OVERDUE = enum.auto()
    GONE_AGENT = enum.auto()
    CHECK_BEFORE_YOU_ANSWER = enum.auto()
    WATCH_SLOT_FREE = enum.auto()
    LEDGER_CHANGED = enum.auto()
    WATCH_MISSING = enum.auto()
    PULL_NEEDS = enum.auto()
    NO_AGENT_RUNNING = enum.auto()
    NEXT = enum.auto()
    SUGGESTION = enum.auto()
    NO_HAND_BACK = enum.auto()
    POLLING = enum.auto()
    SYNCED = enum.auto()
    SYNC_SOURCE_MISSING = enum.auto()
    SYNC_NOT_CONFIGURED = enum.auto()
    NOT_SYNCED = enum.auto()
    COULD_NOT_SYNC = enum.auto()
    NOT_THE_ORCHESTRATOR_CONFIG = enum.auto()
    INCOMPLETE = enum.auto()
    STALE_CLAIM = enum.auto()
    ADOPT_REVIEW = enum.auto()
    MECHANICAL_FIX = enum.auto()
    SLOW_MECHANICAL_FIX = enum.auto()

    @property
    def text(self) -> str:
        """The marker as printed: its name in words.

        Returns:
            The text.
        """
        return SPELLED.get(self, self.name.replace("_", " "))


SPELLED = {
    Marker.PULL_NEEDS: "NEEDS",
    Marker.WATCH_SLOT_FREE: "SLOT FREE",
    Marker.NO_HAND_BACK: "NO HAND-BACK",
    Marker.STALE_CLAIM: "STALE-CLAIM",
    Marker.ADOPT_REVIEW: "ADOPT-REVIEW",
    Marker.MECHANICAL_FIX: "MECHANICAL-FIX",
    Marker.SLOW_MECHANICAL_FIX: "SLOW-MECHANICAL-FIX",
    Marker.CHECK_IN_OVERDUE: "CHECK-IN OVERDUE",
}

# keyword: markup-lines (pitboss#343, pitboss#301): the line of these says what
# happened or what to do, and the class docstring above is their definition, so no
# reference restates them
SELF_EXPLAINED = frozenset(
    {
        Marker.QUEUE_RUN,
        Marker.CANCELLED_STALE_QUEUE_RUN,
        Marker.REMOVED_WORKTREE,
        Marker.CLOSED_SCRATCH_PR,
        Marker.DELETED_SCRATCH_BRANCH,
        Marker.REMOVED_PATH,
        Marker.SWEEP_REMINDER,
        Marker.EMPTY_SLOT,
        Marker.GONE_AGENT,
        Marker.CHECK_BEFORE_YOU_ANSWER,
        Marker.SLOT_IDLE,
        Marker.IDLE_SLOT,
        Marker.CHECK_IN_OVERDUE,
        Marker.NO_HAND_BACK,
        Marker.POLLING,
        Marker.SYNCED,
        Marker.STALE_CLAIM,
        Marker.ADOPT_REVIEW,
        Marker.MECHANICAL_FIX,
        Marker.SLOW_MECHANICAL_FIX,
        Marker.WATCH_SLOT_FREE,
        Marker.LEDGER_CHANGED,
        Marker.WATCH_MISSING,
        Marker.PULL_NEEDS,
        Marker.NO_AGENT_RUNNING,
    }
)

# keyword: one-path: the lines of a waiting item, and every line the decisions do not
# say, are deleted with their markers; the references, which no .md change of that
# pull request touches, may still name these
RETIRED = frozenset(
    {
        "WAIT-FOR-CI",
        "FAILED",
        "RED CAUSE",
        "BLOCKED",
        "UNREADABLE REVIEW",
        "GATE PENDING",
        "DRAFT ROUND",
        "EXECUTION REVIEW EARLY",
        "PINS-ONLY",
        "PINS-ONLY OK",
        "PR STATE",
        "BLOCKS",
        "SUPERSEDED",
        "CONFLICT",
        "FIXED ON BASE",
        "BEHIND",
        "STALL",
        "RULING DUE",
        "PAUSE",
        "RULING UNREADABLE",
        "RULING ESCALATES",
        "PLAN EDITED",
        "PLAN ROW",
        "RULING NO ANALYSIS",
        "REVIEW NOTE",
        "REMOVED FROM QUEUE",
        "DROPPED FROM QUEUE",
        "DRAFT STATE CHANGED",
        "AUTO MERGE OFF",
        "READY TO MERGE",
        "MERGE BY HAND",
        "NOT THE HEAD",
        "HOLD",
        "FIX FIRST",
        "SLOTS",
        "RUNNING",
        "FREE SLOT",
        "START",
        "LEDGER STALE",
    }
)
