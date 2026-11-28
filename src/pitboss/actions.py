"""Actions: each checks the item is at one of the steps it acts for, then writes."""

import dataclasses
from collections.abc import Mapping, Sequence, Set
from typing import Protocol

from . import machine, parse


class Hub(Protocol):
    """The writes: one method, the verb says which."""

    def write(self, ask: "Ask", number: int) -> None:
        """Write one verb on one PR.

        Args:
            ask: the verb and its text.
            number: the PR.
        """


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ask:
    """A verb asked for.

    Attributes:
        verb: a key of ``STEPS``.
        text: a comment body, a label name or the grounds of a review.
        verdict: ``ok`` or ``refused`` for a plan check.
        plan: the grade of a review of the Plan, ``approved`` or ``changes needed``.
        execution: the grade of a review of the Execution, empty for none.
        tickets: the ``Ticket: <ref> <digest>`` lines a review records.
    """

    verb: str
    text: str = ""
    verdict: str = ""
    plan: str = ""
    execution: str = ""
    tickets: Sequence[str] = ()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Done:
    """The action ran.

    Attributes:
        verb: the verb that ran.
    """

    verb: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Refused:
    """The item is not at a step the action is for.

    Attributes:
        wanted: the steps the verb is for.
        found: the step the item is at.
    """

    wanted: Set[machine.Step]
    found: machine.Step


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Invalid:
    """The verb was given a verdict it does not take.

    Attributes:
        verb: the verb.
        allowed: the verdicts it takes.
    """

    verb: str
    allowed: Set[str]


Outcome = Done | Refused | Invalid


GIT = {"push"}
CITES = {"review"}
GRADES = {"approved", "changes needed"}
VERDICTS: Mapping[str, Set[str]] = {"plan-check": {"ok", "refused"}}

STEPS: Mapping[str, Set[machine.Step]] = {
    "merge": {machine.Step.MERGE},
    "undraft": {machine.Step.UNDRAFT},
    "update-branch": {machine.Step.FIX_CONFLICT},
    "rerun": {machine.Step.FIX_CI},
    "dispatch": {machine.Step.RUN_E2E},
    "close": set(),
    "label": set(),
    "comment": set(),
    "push": {
        machine.Step.WORKER,
        machine.Step.FIX_CI,
        machine.Step.FIX_CONFLICT,
        machine.Step.RULING_STEPS,
        machine.Step.PLAN_EDITED,
    },
    "review": {machine.Step.REVIEW},
    "plan-check": {machine.Step.PLAN_CHECK},
    "ruling": {machine.Step.OPUS_RULING},
}
TICKET_STEPS: Mapping[str, Set[machine.Step]] = {
    "pr-create": {machine.Step.OPEN_PR},
}
NEW = "file-ticket"


def settle(
    ask: Ask, hub: Hub, at: tuple[int, machine.Step], wanted: Set[machine.Step]
) -> Outcome:
    """Write when the item is at a wanted step; an empty set wants any.

    Args:
        ask: the verb and its text.
        hub: the writes.
        at: the item's number and its step.
        wanted: the steps the verb is for.

    Returns:
        ``Done``, or ``Refused`` with nothing written.
    """
    number, found = at
    if wanted and found not in wanted:
        return Refused(wanted=wanted, found=found)
    hub.write(ask, number)
    return Done(verb=ask.verb)


def plan_check_text(ask: Ask, pr: parse.Pull) -> str:
    """The comment of a plan check.

    Args:
        ask: the verb and its verdict.
        pr: the PR.

    Returns:
        ``Plan check`` and its verdict line.
    """
    return f"Plan check\nPlan check: {ask.verdict}"


def review_text(ask: Ask, pr: parse.Pull) -> str:
    """The comment of a review, in the form the queue reads.

    Args:
        ask: the grades, the ticket lines and the grounds.
        pr: the PR.

    Returns:
        The comment: head and verdict, grades, digests, tickets, then the grounds.
    """
    who = "a separate reviewer agent, not the author"
    graded = {ask.plan, ask.execution or ask.plan}
    overall = "approved" if graded == {"approved"} else "changes needed"
    execution = [f"Execution: {ask.execution}"] if ask.execution else []
    plan = pr.body.digests[0] if pr.body.digests else ""
    lines = [
        f"Independent review ({who}) of head {pr.head}: {overall}",
        f"Plan: {ask.plan}",
        *execution,
        f"Verdict: {overall}",
        f"Body: {pr.body.whole}",
        f"Plan-digest: {plan}",
        *ask.tickets,
        "",
        ask.text,
    ]
    return "\n".join(lines)


TEXTS = {"review": review_text, "plan-check": plan_check_text}


def composed(ask: Ask, pr: parse.Pull) -> Ask:
    """Write the comment a review or a plan check posts.

    Args:
        ask: the verb and what it carries.
        pr: the PR.

    Returns:
        The ask with the comment as its text; other verbs are as they are.
    """
    make = TEXTS.get(ask.verb)
    return dataclasses.replace(ask, text=make(ask, pr)) if make else ask


def graded(ask: Ask) -> bool:
    """Say whether a review's grades are grades.

    Args:
        ask: the verb and its grades.

    Returns:
        True when the Plan grade is one and the Execution grade is one or empty.
    """
    return ask.plan in GRADES and (not ask.execution or ask.execution in GRADES)


def run(ask: Ask, hub: Hub, pr: parse.Pull, gates: machine.Gates) -> Outcome:
    """Run a verb on a PR when the PR is at a step the verb is for.

    Args:
        ask: the verb and its text; an empty set of steps in ``STEPS`` is any step.
        hub: the writes.
        pr: the PR.
        gates: holds and pressure.

    Returns:
        ``Done``, or ``Refused`` with nothing written.
    """
    allowed = VERDICTS.get(ask.verb, {ask.verdict})
    if ask.verdict not in allowed:
        return Invalid(verb=ask.verb, allowed=allowed)
    if ask.verb in CITES and not graded(ask):
        return Invalid(verb=ask.verb, allowed=GRADES)
    at = (pr.number, machine.pull_step(pr, gates))
    return settle(composed(ask, pr), hub, at, STEPS[ask.verb])


def run_ticket(
    ask: Ask, hub: Hub, ticket: parse.Ticket, pulls: Sequence[parse.Pull]
) -> Outcome:
    """Run a verb on a ticket when the ticket is at a step the verb is for.

    Args:
        ask: the verb and its text.
        hub: the writes.
        ticket: the ticket.
        pulls: the open PRs.

    Returns:
        ``Done``, or ``Refused`` with nothing written.
    """
    found = machine.ticket_step(ticket, pulls)
    return settle(ask, hub, (ticket.number, found), TICKET_STEPS[ask.verb])


def file_ticket(ask: Ask, hub: Hub) -> Outcome:
    """File a new ticket: nothing exists yet, so there is no state to check.

    Args:
        ask: the verb and the title.
        hub: the writes.

    Returns:
        ``Done``.
    """
    hub.write(ask, 0)
    return Done(verb=ask.verb)
