"""What a head's check runs say, decided once (plan 6.1, 4.3: "CI is green").

The one rule, which the parser, the flow, the gate and the reports all take:
passing is an allowlist. A run is finished when its status is ``completed``, and a
finished run has failed unless its conclusion is ``success``, ``neutral`` or
``skipped`` (a cancelled or stale run is red: a run cancelled by a later one is
not current, ``checkruns.latest``). The head's CI is ``result`` of its current runs.
"""

import enum
from typing import Protocol, Sequence

OK_CONCLUSIONS = frozenset({"success", "neutral", "skipped"})
FINISHED_STATUSES = frozenset({"completed"})


class Done(Protocol):
    """What ``any_finished`` and ``all_finished`` read of a run."""

    @property
    def finished(self) -> bool:
        """Return whether it completed."""


class Outcome(Protocol):
    """What ``result`` reads of a check run (``shapes.CheckRun`` has it)."""

    @property
    def finished(self) -> bool:
        """Return whether it completed."""

    @property
    def failed(self) -> bool:
        """Return whether it completed and did not pass (``failed``)."""


class Ci(enum.Enum):
    """The result of the checks on the current head, once finished.

    Attributes:
        GREEN: every check finished and none failed.
        RED: a check failed.
    """

    GREEN = enum.auto()
    RED = enum.auto()


def finished(status: str) -> bool:
    """Whether a check run with this status is done.

    Args:
        status: its status as GitHub wrote it.

    Returns:
        True for ``completed``.
    """
    return status in FINISHED_STATUSES


def failed(status: str, conclusion: object) -> bool:
    """Whether a check run is done and did not pass.

    Args:
        status: its status as GitHub wrote it.
        conclusion: its conclusion (None while it runs).

    Returns:
        True when it finished with a conclusion outside the allowlist.
    """
    return finished(status) and conclusion not in OK_CONCLUSIONS


def result(checks: Sequence[Outcome]) -> Ci | None:
    """The head's CI: the one answer to "is CI green" (plan 6.1).

    Args:
        checks: the head's current check runs.

    Returns:
        RED when a check failed, GREEN when all finished and none failed, None
        while some run or none has started.
    """
    if any(each.failed for each in checks):
        return Ci.RED
    return Ci.GREEN if checks and all_finished(checks) else None


def passed(run: Outcome) -> bool:
    """Whether a run completed and did not fail.

    Args:
        run: the run.

    Returns:
        True when it finished green.
    """
    return run.finished and not run.failed


def any_finished(runs: Sequence[Done]) -> bool:
    """Whether some run completed (none has: the head waits for its CI).

    Args:
        runs: the runs.

    Returns:
        True when one completed.
    """
    return any(each.finished for each in runs)


def all_finished(runs: Sequence[Done]) -> bool:
    """Whether every run completed (true of none).

    Args:
        runs: the runs.

    Returns:
        True when none runs or waits.
    """
    return all(each.finished for each in runs)
