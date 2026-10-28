"""The markers that start the output lines a reader acts on.

A marker's text is its name in words, so the output and the references
spell it the same way; CI checks that the references explain every one.
"""

import enum


class Marker(enum.Enum):
    """A marker at the start of an output line that calls for an action.

    Attributes:
        UNREADABLE: a repository the session cannot read.
        RUNNER_PRESSURE: queue runs wait for runners; hold.
        NO_RUNNER_PRESSURE: nothing waits for a runner.
        CONFLICT: a PR has a merge conflict.
        FAILED: a check failed on a PR's head.
        UNREADABLE_LOG: a failed check whose log could not be read.
        AUTO_MERGE_OFF: auto-merge is off on a healthy PR.
        READY_TO_MERGE: green, clean and approved; arm auto-merge.
        MERGE_BY_HAND: green, clean and approved, in a repository without
            auto-merge.
        QUEUE_RUN: an unfinished queue run, with its age.
        STALE_QUEUE_RUN: a queue run of a superseded group.
        CANCELLED_STALE_QUEUE_RUN: one cancelled.
        COULD_NOT_CANCEL_STALE_QUEUE_RUN: one that could not be.
        STRAGGLER: work that exists only on this machine.
        STALE_WORKTREE: a finished worktree still on disk.
        REMOVED_WORKTREE: one removed.
        COULD_NOT_REMOVE_WORKTREE: one that could not be.
        SWEEP_REMINDER: a question each sweep ends with.
        EMPTY_SLOT: a worker slot with no agent.
        GONE_AGENT: a slot whose agent is no longer running.
        CHECK_BEFORE_YOU_ANSWER: the ledger is kept by hand; check it.
        NEXT: a line of the sorted list of work.
    """

    UNREADABLE = enum.auto()
    RUNNER_PRESSURE = enum.auto()
    NO_RUNNER_PRESSURE = enum.auto()
    CONFLICT = enum.auto()
    FAILED = enum.auto()
    UNREADABLE_LOG = enum.auto()
    AUTO_MERGE_OFF = enum.auto()
    READY_TO_MERGE = enum.auto()
    MERGE_BY_HAND = enum.auto()
    QUEUE_RUN = enum.auto()
    STALE_QUEUE_RUN = enum.auto()
    CANCELLED_STALE_QUEUE_RUN = enum.auto()
    COULD_NOT_CANCEL_STALE_QUEUE_RUN = enum.auto()
    STRAGGLER = enum.auto()
    STALE_WORKTREE = enum.auto()
    REMOVED_WORKTREE = enum.auto()
    COULD_NOT_REMOVE_WORKTREE = enum.auto()
    SWEEP_REMINDER = enum.auto()
    EMPTY_SLOT = enum.auto()
    GONE_AGENT = enum.auto()
    CHECK_BEFORE_YOU_ANSWER = enum.auto()
    NEXT = enum.auto()

    @property
    def text(self) -> str:
        """The marker as printed: its name in words.

        Returns:
            The text.
        """
        return self.name.replace("_", " ")
