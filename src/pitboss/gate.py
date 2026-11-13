"""The act verdict as rows of the decision (keyword: gate; the one-path plan, P8).

A PR at the merge or the undraft step is decided with the rows ``act`` ran before
it merged, armed or undrafted (``gaterows``): when a row stops it, its decision is
the route of the first stop, so the advice and ``act`` are one value. ``act
merge``, ``arm`` and ``undraft`` look the item's decision up (``gateverbs``) and
run only when it is theirs. A recorded ``act override`` lifts one stop at one head,
never a hold, a red, an unread input, a closed PR or a blocker. The rows read the
typed state ``pullstate`` made (plan 6.1): an input not given, a list of another
shape than GitHub documents and a list GitHub answered with an error are stops of
their own, so no row meets a value of another type.
"""

from typing import Sequence

from . import (
    gateevents,
    gatefacts,
    gatefields,
    gatepolicy,
    gaterows,
    steps,
    totalbody,
    totalreview,
)
from .gatestop import Stop
from .pullrecords import GateState

Gate = gatefacts.Gate
ACTIONS = gatefacts.ACTIONS


def _found(action: str, state: GateState, policy: gatepolicy.Policy) -> Sequence[Stop]:
    # every row's stops, in the order act ran them
    kind = gaterows.kind_of(state)
    change = kind == totalbody.CHANGE
    return [
        *gaterows.read_stops(state),
        *gatefields.field_stops(state, action, policy.schema),
        *gaterows.hold_stops(action, state),
        *gaterows.check_stops(action, state),
        *(gaterows.review_stops(action, state, policy) if change else ()),
        *gaterows.body_stops(state, policy),
        *gaterows.merge_stops(action, state),
        *gaterows.diff_stops(action, state, kind),
        *(gaterows.unticketed_stops(state) if change else ()),
        *gaterows.ticket_stops(state),
        *gateevents.event_stops(state, policy.benign),
    ]


def stops_for(
    action: str, gate: Gate, policy: gatepolicy.Policy | None = None
) -> Sequence[Stop]:
    """The stops of an action, after the overrides of the PR's head.

    Args:
        action: ``merge``, ``arm`` or ``undraft``.
        gate: what the PR is gated on.
        policy: the readings (as shipped when None).

    Returns:
        Every stop no override lifts; none when the action may be taken.
    """
    rows, state = policy or gatepolicy.shipped(), gate.state
    alone = gaterows.unread_stops(state) or gaterows.schema_stops(state)
    if alone:
        return alone
    found = _found(action, state, rows)
    lifted = _overridden(state)
    return [
        each
        for each in found
        if each.route in rows.kept or f'stop="{each.line}"' not in lifted
    ]


def stops_of(step: steps.Step, gate: Gate) -> Sequence[Stop]:
    """The stops of the action a step names, as pitboss ships the rows.

    Args:
        step: ``MERGE`` or ``UNDRAFT``.
        gate: what the PR is gated on.

    Returns:
        Every stop no override lifts; none when the action may be taken.
    """
    return stops_for(ACTIONS[step], gate)


def _overridden(state: GateState) -> str:
    # the override records of the head, as one text
    identity, head = state.repository.identity, state.pull.where.head_sha
    timeline = gaterows.listed(state.reads.timeline)
    records = totalreview.act_records(timeline, identity, "override")
    return "\n".join(rest for at, rest in records if at == head)
