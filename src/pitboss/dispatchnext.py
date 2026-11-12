"""``act dispatch-next``: the one next piece of work, by the order of work (pitboss#444).

Keyword: dispatch-next. The slots are the config's and the cap holds (a ledger
slot the config does not name refuses the dispatch); the order is open PRs oldest
first, then tickets by priority and age, a blocked item skipped; a red the base
shares is not the PR's, and a red several PRs share at one step is one ticket, not
a fix round on each; a refused plan-check goes back to its own worker.
"""

import dataclasses
from typing import Mapping, Sequence


class Refused(Exception):
    """The dispatch asked for is not the next one, or nothing may start."""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Item:
    """An open PR or a ticket, as the order reads it.

    Attributes:
        ref: ``owner/name#N`` or a short reference.
        kind: ``pr`` or ``ticket``.
        created: when it was opened (ISO 8601).
        priority: p0 to p3, for a ticket.
        blocked_by: what it waits on, if anything.
        red_check: the check that is red on the PR, if any.
        red_step: the step of that check that failed.
        cause_ticket: the ticket filed for a shared red, if any.
        step: the PR's step (``plan-check-fix`` goes to its own worker).
        worker: the agent that holds the PR.
    """

    ref: str
    kind: str
    created: str
    priority: str = ""
    blocked_by: str = ""
    red_check: str = ""
    red_step: str = ""
    cause_ticket: str = ""
    step: str = ""
    worker: str = ""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class State:
    """What a dispatch reads.

    Attributes:
        cap: the most agents that run at once (the config's).
        slots: the config's slot names.
        ledger: each slot of the ledger and the agent in it ("" for none).
        items: the open PRs and tickets.
        base_red: the checks red on the default branch.
    """

    cap: int
    slots: Sequence[str]
    ledger: Mapping[str, str]
    items: Sequence[Item]
    base_red: Sequence[str] = ()


def order(items: Sequence[Item]) -> Sequence[Item]:
    """The order of work.

    Args:
        items: the open PRs and tickets.

    Returns:
        Open PRs oldest first, then tickets by priority, then by age; a blocked
        item is left out.
    """
    free = [each for each in items if not each.blocked_by]
    return sorted(
        free,
        key=lambda each: (
            each.kind != "pr",
            each.priority if each.kind != "pr" else "",
            each.created,
        ),
    )


def _slots(state: State) -> None:
    unknown = sorted(set(state.ledger) - set(state.slots))
    if unknown:
        raise Refused(
            f"the ledger holds slot {unknown[0]}, which the config does not name"
        )
    running = sum(1 for agent in state.ledger.values() if agent)
    if running >= state.cap:
        raise Refused(f"{running} agents run and the cap is {state.cap}")
    if len(state.slots) != state.cap:
        raise Refused(
            f"the config names {len(state.slots)} slots and the cap is {state.cap}"
        )


def _red(state: State, item: Item) -> None:
    if not item.red_check:
        return
    if item.red_check in state.base_red:
        raise Refused(
            f"{item.red_check} is red on the default branch too: the cause is not this PR"
            " (one ticket for the cause)"
        )
    same = [
        each.ref
        for each in state.items
        if each is not item
        and (each.red_check, each.red_step) == (item.red_check, item.red_step)
    ]
    if same and not item.cause_ticket:
        raise Refused(
            f"{item.red_check} fails at the same step on {same[0]}: one cause, one ticket, no fix round on each"
        )


def next_item(state: State, want: str = "", agent: str = "") -> Item:
    """The next piece of work, when one may start.

    Args:
        state: the slots, the ledger and the items.
        want: the item the caller means ("" for any); it must be the first.
        agent: the agent that would take it.

    Returns:
        The first item of the order.

    Raises:
        Refused: a slot the config does not name, the cap reached, nothing free,
            another item first, a red that is not the PR's or is shared, or a
            refused plan-check given to another worker.
    """
    _slots(state)
    found = order(state.items)
    if not found:
        raise Refused("nothing in the order is free")
    item = found[0]
    if want and want != item.ref:
        raise Refused(f"the next in the order is {item.ref}, not {want}")
    _red(state, item)
    if item.step == "plan-check-fix" and agent != item.worker:
        raise Refused(
            f"a refused plan-check goes back to its own worker ({item.worker}), not a new agent"
        )
    return item
