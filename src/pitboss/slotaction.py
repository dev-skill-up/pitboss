"""What ``slots`` does (keyword: slots)."""

import enum
from .textparts import hyphenated


class Action(enum.Enum):
    """What ``slots`` does.

    Attributes:
        SHOW: print the ledger.
        SET: put an agent in an empty slot (SLOT AGENT TASK, --kind), or a
            fix round on the agent it holds.
        FREE: empty a slot (SLOT), then print the line ``NEXT`` gives it.
        ADD: add a slot (SLOT MODEL).
        REMOVE: remove an empty slot (SLOT).
        FAILED: record that a model failed a ticket (TICKET MODEL).
        CHECK: list the slots whose agent is gone (--running NAME ...); an
            optional number N exits 1 when the ledger has fewer than N rows.
        NEXT: print what to start next, and what each empty slot takes; with a
            ticket or PR (TICKET), only its brief and its place in the order.
        WAIT: say a slot's agent waits (SLOT).
        RESUME: say a slot's agent runs again (SLOT).
        REPORT: print the share of slot time in each state (--since, --until).
        TIME: print the worker minutes of each ticket (--since, --until).
        HEARD: say a slot's agent handed back or notified (SLOT); each is
            logged as a hand-back (keyword: log-line).
        DEVIATION: record the ``Deviation:`` lines of a review saved in a
            file on the worker's ticket (TICKET FILE; keyword: deviations).
        WATCH: keep the ledger from the session's agent transcripts, each
            ``--interval`` seconds for ``--rounds`` rounds (0: until stopped); run
            by the Monitor tool (keyword: slots-watch, pitboss#415).
        FREE_CHECK: print ``IDLE SLOT`` when a slot has been free for over ten
            minutes, else nothing (keyword: free-check, pitboss#450).
        CHECKIN: record that the status was posted just now (keyword: check-in,
            pitboss#450).
        TASKLIST: print the task list from the ledger and GitHub, in the format
            of ``update_progress_checklist`` (keyword: task-list, pitboss#471).
    """

    SHOW = enum.auto()
    SET = enum.auto()
    FREE = enum.auto()
    ADD = enum.auto()
    REMOVE = enum.auto()
    FAILED = enum.auto()
    CHECK = enum.auto()
    NEXT = enum.auto()
    WAIT = enum.auto()
    RESUME = enum.auto()
    REPORT = enum.auto()
    TIME = enum.auto()
    HEARD = enum.auto()
    DEVIATION = enum.auto()
    WATCH = enum.auto()
    FREE_CHECK = enum.auto()
    CHECKIN = enum.auto()
    TASKLIST = enum.auto()

    @property
    def word(self) -> str:
        """The action as typed.

        Returns:
            The word.
        """
        return hyphenated(self.name)
