"""State machine: a parsed PR or ticket (and the gates) to its one next step. Pure."""

import dataclasses
import enum
from collections.abc import Sequence

from . import parse


class Step(enum.Enum):
    """What happens next.

    Attributes:
        WORKER: a worker writes code.
        REVIEW: a reviewer grades the head.
        OPUS_RULING: an Opus agent rules.
        FIX_RULING: the newest ruling has no readable ``Ruling:`` line.
        RULING_STEPS: the worker does the steps of the newest ruling.
        OWNER: the newest ruling escalates to the owner.
        PLAN_CHECK: no clean Plan check is recorded.
        SEND_BACK_PLAN_CHECK: the Plan check refused the Plan.
        PLAN_EDITED: the approved Plan was edited.
        RUN_E2E: dispatch the checks of a draft that touches e2e.
        UNDRAFT: mark a approved draft ready.
        FIX_CI: a check of the head is red.
        FIX_CONFLICT: the head conflicts with the base.
        WAIT: checks are still running.
        HELD: a hold or the runner pressure withholds a write.
        MERGE: the PR merges.
        OPEN_PR: a ticket has no PR.
        DONE: a ticket is closed.
        WAIT_FOR_PR: a ticket has a PR that fixes it.
    """

    WORKER = enum.auto()
    REVIEW = enum.auto()
    OPUS_RULING = enum.auto()
    FIX_RULING = enum.auto()
    RULING_STEPS = enum.auto()
    OWNER = enum.auto()
    PLAN_CHECK = enum.auto()
    SEND_BACK_PLAN_CHECK = enum.auto()
    PLAN_EDITED = enum.auto()
    RUN_E2E = enum.auto()
    UNDRAFT = enum.auto()
    FIX_CI = enum.auto()
    FIX_CONFLICT = enum.auto()
    WAIT = enum.auto()
    HELD = enum.auto()
    MERGE = enum.auto()
    OPEN_PR = enum.auto()
    DONE = enum.auto()
    WAIT_FOR_PR = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Gates:
    """What the caller read of the world outside the PR.

    Attributes:
        hold: whether a hold is on.
        pressure: whether the runners are under pressure.
        quiet: whether the quiet period after a push lasts.
    """

    hold: bool = False
    pressure: bool = False
    quiet: bool = False


WRITES = frozenset({Step.MERGE, Step.UNDRAFT, Step.RUN_E2E})


def at_head(pr: parse.Pull) -> Sequence[parse.Review]:
    """The reviews that name the head of the PR.

    Args:
        pr: the PR.

    Returns:
        Them, oldest first.
    """
    return [
        r
        for r in pr.thread.reviews
        if pr.head.startswith(r.sha) or r.sha.startswith(pr.head)
    ]


def ruled(pr: parse.Pull) -> Step | None:
    """The step a ruling asks for, when the newest event is one.

    Args:
        pr: the PR.

    Returns:
        The step, None when the newest event is not a ruling.
    """
    order = pr.thread.order
    asks = {"ruling-unreadable": Step.FIX_RULING}
    if order and order[-1] == "ruling":
        words = pr.thread.rulings[-1]
        return Step.OWNER if words.startswith("escalate") else Step.RULING_STEPS
    return asks.get(order[-1]) if order else None


def checked(pr: parse.Pull) -> Step | None:
    """The step the Plan check asks for.

    Args:
        pr: the PR.

    Returns:
        The step, None when the Plan check is clean.
    """
    marks = [k for k in pr.thread.order if k.startswith("plancheck")]
    if not marks:
        return Step.PLAN_CHECK
    return Step.SEND_BACK_PLAN_CHECK if marks[-1] == "plancheck-refused" else None


def pull_step(pr: parse.Pull, gates: Gates = Gates()) -> Step:
    """The step of a PR.

    Args:
        pr: the PR.
        gates: holds and pressure.

    Returns:
        The step.
    """
    step = _step(pr)
    held = gates.hold or "hold" in pr.labels
    pressed = (gates.pressure or gates.quiet) and step is not Step.UNDRAFT
    return Step.HELD if step in WRITES and (held or pressed) else step


def _graded(pr: parse.Pull, last: parse.Review) -> Step:
    grades = (last.plan, last.execution)
    if "changes needed" in grades:
        rejected = sum(r.execution == "changes needed" for r in pr.thread.reviews)
        return Step.OPUS_RULING if rejected >= 2 else Step.WORKER
    if last.execution != "approved":
        return Step.WORKER if last.plan == "approved" else Step.REVIEW
    return _ready(pr)


def _ready(pr: parse.Pull) -> Step:
    e2e = any(f.startswith("e2e/") for f in pr.files)
    if pr.draft:
        return Step.UNDRAFT if "e2e" in pr.labels or not e2e else Step.RUN_E2E
    return Step.MERGE if pr.checks and set(pr.checks) == {"green"} else Step.WAIT


def _step(pr: parse.Pull) -> Step:
    asked = ruled(pr)
    if asked is None and not pr.body.sections:
        return Step.WORKER
    if asked is None and pr.conflict:
        return Step.FIX_CONFLICT
    if asked is None and "red" in pr.checks:
        return Step.FIX_CI
    asked = asked or checked(pr)
    mine = at_head(pr)
    if asked is not None:
        return asked
    if not mine:
        return Step.REVIEW
    pinned = mine[-1].plan_digest
    if pinned and pinned != pr.body.digest:
        return Step.PLAN_EDITED
    return _graded(pr, mine[-1])


def ticket_step(t: parse.Ticket, pulls: Sequence[parse.Pull]) -> Step:
    """The step of a ticket.

    Args:
        t: the ticket.
        pulls: the open PRs.

    Returns:
        The step.
    """
    if not t.is_open:
        return Step.DONE
    if any(t.number in p.body.closes for p in pulls):
        return Step.WAIT_FOR_PR
    return Step.OPEN_PR
