"""The input whose re-read ends each wait (keyword: idle-event, #524).

A PR that no actor takes waits on an event (``steps.Idle`` is one member for each),
and an event is a change of one input pitboss reads on every run. ``source_of`` is
total, closed by ``assert_never``, so an ``Idle`` with no input does not type-check;
``Ended`` is the one move with no event, and no ``Idle`` member is it.
"""

import enum
from typing import assert_never

from . import steps


class Source(enum.Enum):
    """An input whose change ends a wait.

    Attributes:
        CHECK_RUNS: the check runs of the head.
        RUNNER_QUEUE: the runners' queue of the repository.
        BLOCKERS: the state of the PRs and issues a PR names as blockers.
        CLOCK: the time, against the window an approved draft waits for.
        SHARED_GROUPS: the PRs of a shared red, and which of them merged.
    """

    CHECK_RUNS = enum.auto()
    RUNNER_QUEUE = enum.auto()
    BLOCKERS = enum.auto()
    CLOCK = enum.auto()
    SHARED_GROUPS = enum.auto()


def source_of(wait: steps.Idle) -> Source:
    """The input whose re-read can end a wait.

    Args:
        wait: what the PR waits on.

    Returns:
        The input.
    """
    match wait:
        case steps.Idle.CI_RUN:
            return Source.CHECK_RUNS
        case steps.Idle.RUNNER_PRESSURE:
            return Source.RUNNER_QUEUE
        case steps.Idle.BLOCKER_OPEN:
            return Source.BLOCKERS
        case steps.Idle.UNDRAFT_WINDOW:
            return Source.CLOCK
        case steps.Idle.LOWER_PR_FIXES:
            return Source.SHARED_GROUPS
        case _:  # pragma: no cover
            assert_never(wait)
