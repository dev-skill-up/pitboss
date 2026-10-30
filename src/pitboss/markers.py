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
        WAIT_FOR_CI: a PR's head has no completed check run.
        CONFLICT: a PR has a merge conflict.
        FAILED: a check failed on a PR's head.
        UPDATE: a PR is behind the base with every check finished.
        STALL: a relock PR whose check has been red for over four hours.
        RULING_DUE: a PR whose review rounds hit the changes-needed limit and
            has no Opus ruling.
        PAUSE: a PR that needed changes again after its Opus ruling.
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
        SLOTS_FREE: slots are free and work is queued; a wake-up is required.
        GONE_AGENT: a slot whose agent is no longer running.
        CHECK_BEFORE_YOU_ANSWER: the ledger is kept by hand; check it.
        NEXT: a line of the sorted list of work.
        NO_HAND_BACK: an agent started over ten minutes ago that has said nothing.
    """

    UNREADABLE = enum.auto()
    RUNNER_PRESSURE = enum.auto()
    NO_RUNNER_PRESSURE = enum.auto()
    WAIT_FOR_CI = enum.auto()
    CONFLICT = enum.auto()
    FAILED = enum.auto()
    UPDATE = enum.auto()
    STALL = enum.auto()
    RULING_DUE = enum.auto()
    PAUSE = enum.auto()
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
    SLOTS_FREE = enum.auto()
    GONE_AGENT = enum.auto()
    CHECK_BEFORE_YOU_ANSWER = enum.auto()
    NEXT = enum.auto()
    NO_HAND_BACK = enum.auto()

    @property
    def text(self) -> str:
        """The marker as printed: its name in words.

        Returns:
            The text.
        """
        return SPELLED.get(self, self.name.replace("_", " "))


SPELLED = {
    Marker.NO_HAND_BACK: "NO HAND-BACK",
    Marker.WAIT_FOR_CI: "WAIT-FOR-CI",
}
