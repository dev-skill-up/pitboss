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
        verdict: ``approved`` or ``changes needed`` for a review, ``ok`` or
            ``refused`` for a plan check.
    """

    verb: str
    text: str = ""
    verdict: str = ""


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

VERDICTS: Mapping[str, Set[str]] = {
    "review": {"approved", "changes needed"},
    "plan-check": {"ok", "refused"},
}

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


def composed(ask: Ask, pr: parse.Pull) -> Ask:
    """Write the comment a review or a plan check posts, in the form the queue reads.

    Args:
        ask: the verb, its verdict and its grounds.
        pr: the PR.

    Returns:
        The ask with the comment as its text; other verbs are as they are.
    """
    who = "a separate reviewer agent, not the author"
    plan = pr.body.digests[0] if pr.body.digests else ""
    forms = {
        "plan-check": ["Plan check", f"Plan check: {ask.verdict}"],
        "review": [
            f"Independent review ({who}) of head {pr.head}: {ask.verdict}",
            f"Plan: {ask.verdict}",
            f"Verdict: {ask.verdict}",
            f"Body: {pr.body.whole}",
            f"Plan-digest: {plan}",
            "",
            ask.text,
        ],
    }
    lines = forms.get(ask.verb)
    return dataclasses.replace(ask, text="\n".join(lines)) if lines else ask


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
