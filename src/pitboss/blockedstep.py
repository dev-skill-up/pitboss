"""The step a PR's blockers call for, from its closure as read (keyword: blocked-by).

``blockedby`` reads the closure (each blocker a PR's ``Blocked-by:`` lines name, and
whether a chain of them leads back to it); ``decide`` gives the PR the step this
module says, with no read of its own (the one-path plan, 6.1: the settlers are
rows of ``decide``).
"""

import dataclasses
import enum
from typing import Protocol, Sequence

from . import config, pullref, shapes, steps

FIX = steps.worker(steps.Task.FIX_BLOCKED_BY)  # a closed blocker, or a loop


class AtStep(Protocol):
    """What the settlers read of a PR (``pullfacts.PullFacts`` has it)."""

    @property
    def repo(self) -> config.Repo:
        """Return its repository."""

    @property
    def pull(self) -> shapes.Pull:
        """Return the PR."""

    @property
    def checks(self) -> Sequence[shapes.CheckRun]:
        """Return the check runs of its head."""

    @property
    def step(self) -> steps.Move:
        """Return the step its facts give."""


class State(enum.Enum):
    """What a blocker is.

    Attributes:
        OPEN: still open.
        MERGED: merged.
        CLOSED: closed without merging.
        UNREADABLE: the API does not give it.
    """

    OPEN = enum.auto()
    MERGED = enum.auto()
    CLOSED = enum.auto()
    UNREADABLE = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Blocker:
    """A ticket or PR another PR waits for.

    Attributes:
        reference: ``owner/name#number``.
        state: what it is.
        merged_at: when it merged (ISO 8601), else empty.
        body: its text.
    """

    reference: str
    state: State
    merged_at: str
    body: str


def is_open(blocker: Blocker) -> bool:
    """Whether a blocker is still open: the one reading of its state (plan 6.1).

    Args:
        blocker: the blocker as read.

    Returns:
        True when it is open.
    """
    return blocker.state is State.OPEN


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Closure:
    """What a PR's ``Blocked-by:`` lines name, as read.

    Attributes:
        found: each blocker it names, in the order named.
        looped: whether a chain of blockers leads back to the PR.
    """

    found: Sequence[Blocker]
    looped: bool


def open_named(closure: Closure) -> Sequence[str]:
    """The open items a PR's ``Blocked-by:`` lines name (``is_open`` of each).

    Args:
        closure: what its lines name, as read.

    Returns:
        Their references, in the order named.
    """
    return [each.reference for each in closure.found if is_open(each)]


CLOSED = frozenset({State.CLOSED, State.UNREADABLE})


def _red_since(pull: AtStep, merged: str) -> bool:
    # the head is red, and every failed check ended before the blockers merged
    failing = pullref.failed_checks(pull)
    last = max(map(_ended, failing), default="")
    return (
        bool(last) and last < merged and steps.Task.FIX_CI is steps.task_of(pull.step)
    )


def _ended(check: shapes.CheckRun) -> str:
    return check.completed_at


def verdict(pull: AtStep, found: Sequence[Blocker]) -> steps.Move | None:
    """The step a PR has because of what it waits for.

    Args:
        pull: the PR.
        found: its blockers as read, with no loop through it.

    Returns:
        The step; None when the PR keeps its own.
    """
    shut = [each.reference for each in found if each.state in CLOSED]
    live = [each.reference for each in found if is_open(each)]
    # keyword: one-path: no actor takes the PR while a blocker it names is open
    when = max((each.merged_at for each in found), default="")
    if shut:
        return FIX
    if live:
        return steps.IDLE
    if _red_since(pull, when):
        return steps.worker(steps.Task.AFTER_BLOCKER)
    return None


def step_of(pull: AtStep, closure: Closure) -> steps.Move | None:
    """The step a PR's blockers give it, from its closure.

    Args:
        pull: the PR, at the step its own facts give.
        closure: its blockers as read.

    Returns:
        The step; None when the PR keeps its own (no blocker, a pause or hold of
        its own (no actor takes it), or an owed ruling).
    """
    kept = isinstance(pull.step, steps.Idle)  # no actor takes it: it stays so
    if not closure.found or kept or steps.step_is(pull.step, steps.UNRESOLVED):
        return None
    if closure.looped:  # a loop is fixed, never waited on
        return FIX
    return verdict(pull, closure.found)
