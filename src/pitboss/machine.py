"""State machine: a parsed PR or ticket to its one next step. Pure."""

import enum

from . import parse


class Step(enum.Enum):
    """What happens next."""

    WORKER = enum.auto()
    REVIEW = enum.auto()
    OPUS_RULING = enum.auto()
    OWNER = enum.auto()
    UNDRAFT = enum.auto()
    FIX_CI = enum.auto()
    FIX_CONFLICT = enum.auto()
    WAIT = enum.auto()
    MERGE = enum.auto()
    OPEN_PR = enum.auto()
    DONE = enum.auto()
    WAIT_FOR_PR = enum.auto()


def pull_step(pr: parse.Pull) -> Step:
    """The step of a PR.

    Args:
        pr: the PR.

    Returns:
        The step.
    """
    if pr.rulings and pr.rulings[-1].startswith("escalate"):
        return Step.OWNER
    if pr.conflict:
        return Step.FIX_CONFLICT
    if "red" in pr.checks:
        return Step.FIX_CI
    mine = [r for r in pr.reviews if pr.head.startswith(r.sha) or r.sha.startswith(pr.head)]
    if not mine:
        return Step.REVIEW
    last = mine[-1]
    if "changes needed" in (last.plan, last.execution):
        rejected = sum(r.execution == "changes needed" for r in pr.reviews)
        return Step.OPUS_RULING if rejected >= 2 else Step.WORKER
    if last.execution != "approved":
        return Step.WORKER if last.plan == "approved" else Step.REVIEW
    if pr.draft:
        return Step.UNDRAFT
    return Step.MERGE if pr.checks and set(pr.checks) == {"green"} else Step.WAIT


def ticket_step(t: parse.Ticket, pulls: list[parse.Pull]) -> Step:
    """The step of a ticket.

    Args:
        t: the ticket.
        pulls: the open PRs.

    Returns:
        The step.
    """
    if not t.open:
        return Step.DONE
    if any(t.number in p.fixes for p in pulls):
        return Step.WAIT_FOR_PR
    return Step.OPEN_PR
