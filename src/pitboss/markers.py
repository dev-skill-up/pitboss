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
        UNREADABLE_REVIEW: a trusted comment with a Verdict, Plan or Execution
            line whose first line is not the repository's review first line.
        GATE_PENDING: a gated repository's review gate (the status
            ``adversarial-review``) is not success on a PR's head, whatever
            the PR's ``review=`` says.
        RUNNER_PRESSURE: queue runs wait for runners; hold.
        NO_RUNNER_PRESSURE: nothing waits for a runner.
        WAIT_FOR_CI: a PR's head has no completed check run.
        DRAFT_ROUND: a draft that needs a review or a fix.
        RUN_E2E_BEFORE_APPROVAL: a draft whose Plan is approved and whose diff
            touches what the e2e suite runs on, with no completed dispatched
            run at its head (its own run skipped e2e): dispatch the check
            workflow on its branch.
        EXECUTION_REVIEW_EARLY: an Execution review written while the PR was a
            draft, or before the last check of the reviewed head completed green
            (pitboss#369); it does not count, and one Execution review is due.
        FOLDED_PR: an open PR whose body closes several tickets and cites no
            Opus ruling that allows it.
        PINS_ONLY: a green PR that only moves pins, at a review step, whose
            pins-check command did not print ``OK``; it is reviewed as before
            (keyword: pins-only, pitboss#34).
        PINS_ONLY_OK: a green PR that only moves pins whose pins-check command
            printed ``OK``: no review is offered, the merge is.
        PR_STATE: the line of an open PR in ``slots next``: its next step.
        BLOCKED: a commit status of a PR's head failed; the line names the
            status, its link and, for ``text-lint``, whether the finding is about
            the body or the pin. Also ``BLOCKED <ticket> by <blocker>``: a ticket
            that says it cannot be worked on until an open ticket or PR (its blockers
            are joined by commas), also a PR whose ticket does, or whose newest
            trusted ``Plan check`` refuses the Plan and names them: the PR has no
            step until the blocker merges (keyword: blocked-pull, plan-refusal,
            pitboss#388). A PR whose failed check is ``canonical-files`` with a hash
            that ``tools/pin-audit/allowlist.txt`` of repository-prototype does not
            list is blocked by the open repository-prototype PR that adds the
            line, else by the ticket that asks for it, and its line ends with
            ``; allowlist line: <the line>`` (keyword: allowlist-miss, pitboss#448).
        BLOCKS: ``BLOCKS <ticket>: blocks <tickets>; ranked <label>, opened
            <date>``, or ``BLOCKS <ticket> (PR <pr>): ...`` when an open PR
            stands for the ticket: a ticket that blocks another is ranked with
            the label and the creation time of the oldest item that waits for it
            (keyword: blocks-line, pitboss#388).
        SUPERSEDED: ``SUPERSEDED <ticket>``: a ticket marked as superseded, in
            ``[slots] superseded`` or by a comment line; no start is offered for
            it (keyword: superseded-ticket, pitboss#388).
        PROMOTE: ``PROMOTE <ticket> to <label>: caused K corrections (<list>)``:
            K other tickets and PRs say ``Caused by`` or ``Cause:`` the ticket;
            it is ranked as the top label with its own age, and the label stays
            the owner's to change (keyword: promote-line, pitboss#388).
        CONFLICT: a PR has a merge conflict.
        FAILED: a check failed on a PR's head.
        RED_CAUSE: the log of a failed check and the rule that its cause is the
            answer, never a new run (keyword: red-cause, pitboss#420).
        FIXED_ON_BASE: a PR of a merge-queue repository is red only from checks
            that passed on the base since (pitboss#314): enqueue it, or request
            its review.
        UPDATE: a PR is behind the base with every check finished.
        BEHIND: a PR whose review approved and whose checks passed is behind
            the base (pitboss#369); no merge is offered.
        STALL: a relock PR whose check has been red for over four hours.
        RULING_DUE: a PR whose review rounds hit the changes-needed limit and
            has no Opus ruling.
        PAUSE: a PR that needed changes again after its Opus ruling.
        RULING_UNREADABLE: a PR whose newest Opus ruling comment has no
            readable ``Ruling: <word>`` second line.
        RULING_ESCALATES: a PR whose Opus ruling escalated to the owner.
        PLAN_EDITED: a PR whose Plan section differs from the Plan its newest
            approving review read, with no Opus ruling that allows the edit.
        PLAN_ROW: a PR whose numbered Plan row lacks the whole command of the
            Evidence line of the same number in backticks (pitboss#259), unless a
            trusted review approved that Plan (pitboss#296).
        RULING_NO_ANALYSIS: a PR whose newest Opus ruling comment has no
            ``How we got here`` section.
        REVIEW_NOTE: an approved PR whose newest review has a ``Notes``
            paragraph that names a case not handled.
        OPUS_RULINGS_DAILY: Opus ruling comments are dated since the last
            summary and none is recorded for the Pacific day.
        REMOVED_FROM_QUEUE: the merge queue removed a PR, and why.
        DROPPED_FROM_QUEUE: a PR that was armed or queued lost auto-merge with no
            removal event, and is neither queued nor merged (keyword:
            dropped-from-queue, quire#1110).
        WAIT_FOR_HOLD: a runner-pressure hold or its quiet period withholds the
            action a PR's line asks for (keyword: hold-gate, quire#1110).
        FIX_FIRST: a cheap check of the head is red (``text-lint``, the review gate,
            ``canonical-files``, the Plan check, the review form, the pins-check),
            so the step that would spend runner time waits for its fix (keyword:
            known-red, quire#1120).
        STALE_CLAIM: a PR's body names a head that is not its head, so a worker's
            claim of a push was not true (keyword: claim-readback, quire#1115).
        ADOPT_REVIEW: a PR's body says the ``adopt`` script made it, so its review is
            of the script, not of the diff (keyword: adopt-made, pitboss#423).
        MECHANICAL_FIX: a PR's red is a failed plan job or a fixture expectation
            mismatch, which one push fixes and a push to a draft-free hold may
            exempt (keyword: mechanical-fix, pitboss#32).
        SLOW_MECHANICAL_FIX: a mechanical red whose fix push has not happened within
            the configured minutes.
        DRAFT_STATE_CHANGED: a PR's draft state changed after the sweep marked it
            ready (keyword: draft-moves, pitboss#355).
        AUTO_MERGE_OFF: auto-merge is off on a healthy PR.
        READY_TO_MERGE: green, clean and approved; arm auto-merge.
        MERGE_BY_HAND: green, clean and approved, in a repository without
            auto-merge.
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
        SLOTS: the first line of ``slots next``: the running agents against the
            cap and the free slots (keyword: slots-header, pitboss#415).
        RUNNING: a line for each running agent by kind (``RUNNING worker <ticket>``,
            ``RUNNING fix round <PR>``, ``RUNNING reviewer <PR>``).
        FREE_SLOT: ``slots next`` with fewer running agents than the cap: dispatch.
        START: the first dispatchable ``NEXT`` line, printed when a slot is free.
        LEDGER_STALE: ``slots next`` was given no ``--running`` and the ledger
            holds rows nobody confirmed.
        NOT_THE_HEAD: ``next TICKET`` prints a worker brief for a ticket that is not
            the first startable item of ``slots next`` (keyword: not-the-head).
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
        HOLD: the owner's hold on new pull requests applies to
            a repository (``[holds] new_pull_requests``), with its open count.
        HELD_TICKET: a ticket of a held repository, which ``slots next`` does not offer.
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
    """

    OUTDATED = enum.auto()
    UNREADABLE = enum.auto()
    UNREADABLE_REVIEW = enum.auto()
    GATE_PENDING = enum.auto()
    RUNNER_PRESSURE = enum.auto()
    NO_RUNNER_PRESSURE = enum.auto()
    WAIT_FOR_CI = enum.auto()
    DRAFT_ROUND = enum.auto()
    RUN_E2E_BEFORE_APPROVAL = enum.auto()
    EXECUTION_REVIEW_EARLY = enum.auto()
    FOLDED_PR = enum.auto()
    PINS_ONLY = enum.auto()
    PINS_ONLY_OK = enum.auto()
    PR_STATE = enum.auto()
    BLOCKED = enum.auto()
    BLOCKS = enum.auto()
    SUPERSEDED = enum.auto()
    PROMOTE = enum.auto()
    CONFLICT = enum.auto()
    FAILED = enum.auto()
    RED_CAUSE = enum.auto()
    FIXED_ON_BASE = enum.auto()
    UPDATE = enum.auto()
    BEHIND = enum.auto()
    STALL = enum.auto()
    RULING_DUE = enum.auto()
    PAUSE = enum.auto()
    RULING_UNREADABLE = enum.auto()
    RULING_ESCALATES = enum.auto()
    PLAN_EDITED = enum.auto()
    PLAN_ROW = enum.auto()
    RULING_NO_ANALYSIS = enum.auto()
    REVIEW_NOTE = enum.auto()
    OPUS_RULINGS_DAILY = enum.auto()
    REMOVED_FROM_QUEUE = enum.auto()
    DROPPED_FROM_QUEUE = enum.auto()
    WAIT_FOR_HOLD = enum.auto()
    DRAFT_STATE_CHANGED = enum.auto()
    AUTO_MERGE_OFF = enum.auto()
    READY_TO_MERGE = enum.auto()
    MERGE_BY_HAND = enum.auto()
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
    SLOTS = enum.auto()
    RUNNING = enum.auto()
    FREE_SLOT = enum.auto()
    START = enum.auto()
    LEDGER_STALE = enum.auto()
    NOT_THE_HEAD = enum.auto()
    WATCH_SLOT_FREE = enum.auto()
    LEDGER_CHANGED = enum.auto()
    WATCH_MISSING = enum.auto()
    PULL_NEEDS = enum.auto()
    NO_AGENT_RUNNING = enum.auto()
    NEXT = enum.auto()
    SUGGESTION = enum.auto()
    HOLD = enum.auto()
    HELD_TICKET = enum.auto()
    NO_HAND_BACK = enum.auto()
    POLLING = enum.auto()
    SYNCED = enum.auto()
    SYNC_SOURCE_MISSING = enum.auto()
    SYNC_NOT_CONFIGURED = enum.auto()
    NOT_SYNCED = enum.auto()
    COULD_NOT_SYNC = enum.auto()
    NOT_THE_ORCHESTRATOR_CONFIG = enum.auto()
    INCOMPLETE = enum.auto()
    FIX_FIRST = enum.auto()
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
    Marker.HELD_TICKET: "HELD",
    Marker.PINS_ONLY: "PINS-ONLY",
    Marker.PINS_ONLY_OK: "PINS-ONLY OK",
    Marker.NO_HAND_BACK: "NO HAND-BACK",
    Marker.WAIT_FOR_CI: "WAIT-FOR-CI",
    Marker.WAIT_FOR_HOLD: "WAIT-FOR-HOLD",
    Marker.FIX_FIRST: "FIX FIRST",
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
        Marker.UNREADABLE_REVIEW,
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
        Marker.HELD_TICKET,
        Marker.SLOT_IDLE,
        Marker.IDLE_SLOT,
        Marker.CHECK_IN_OVERDUE,
        Marker.NO_HAND_BACK,
        Marker.POLLING,
        Marker.SYNCED,
        Marker.EXECUTION_REVIEW_EARLY,
        Marker.BEHIND,
        Marker.READY_TO_MERGE,
        Marker.WAIT_FOR_HOLD,
        Marker.FIX_FIRST,
        Marker.STALE_CLAIM,
        Marker.ADOPT_REVIEW,
        Marker.MECHANICAL_FIX,
        Marker.SLOW_MECHANICAL_FIX,
        Marker.DROPPED_FROM_QUEUE,
        Marker.MERGE_BY_HAND,
        Marker.AUTO_MERGE_OFF,
        Marker.DRAFT_STATE_CHANGED,
        Marker.BLOCKS,
        Marker.SUPERSEDED,
        Marker.PROMOTE,
        Marker.RED_CAUSE,
        Marker.SLOTS,
        Marker.RUNNING,
        Marker.FREE_SLOT,
        Marker.START,
        Marker.LEDGER_STALE,
        Marker.NOT_THE_HEAD,
        Marker.WATCH_SLOT_FREE,
        Marker.LEDGER_CHANGED,
        Marker.WATCH_MISSING,
        Marker.PULL_NEEDS,
        Marker.NO_AGENT_RUNNING,
    }
)
