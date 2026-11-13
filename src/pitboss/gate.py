"""The act verdict as rows of the decision (keyword: gate; the one-path plan, P8).

A PR at the merge or the undraft step is decided with the rows ``act`` ran before
it merged, armed or undrafted (``gaterows``): when a row stops it, its decision is
the route of the first stop, so the advice and ``act`` are one value. ``act
merge``, ``arm`` and ``undraft`` look the item's decision up (``gateverbs``) and
run only when it is theirs. A recorded ``act override`` lifts one stop at one head,
never a hold, a red, an unread input, a closed PR or a blocker.
"""

from typing import Mapping, Sequence

from . import (
    answer,
    gateevents,
    gatefacts,
    gatepolicy,
    gaterows,
    gateverbs,
    steps,
    totalbody,
    totalreview,
)
from .gatestop import Route, Stop
from .totaljson import JsonMap, listed, name_at, text

Gate = gatefacts.Gate
OWNER = answer.Actor.OWNER
ORCHESTRATOR = answer.Actor.ORCHESTRATOR
WORKER = answer.Actor.WORKER
REVIEWER = answer.Actor.REVIEWER
UNREAD_SAID = gateverbs.UNREAD_SAID
TRIAGE = gateverbs.TRIAGE
# who acts on each stop, and how; None when no actor takes it now (a hold, a run,
# a blocker, a closed PR, another queue's PR, GitHub not decided); every route has
# its row (a nox check, P8)
Actors = Mapping[Route, tuple[answer.Actor, str] | None]
ROUTES: Actors = {
    Route.HOLD: None,
    Route.RUNNING: None,
    Route.BLOCKED: None,
    Route.CLOSED: None,
    Route.FOREIGN: None,
    Route.UNDECIDED: None,
    Route.PAUSED: (OWNER, "remove paused-owner"),
    Route.LOCK: (OWNER, "unlock the conversation"),
    Route.REVIEWERS: (OWNER, "give or withdraw the requested human review"),
    Route.CHANGES_REQUESTED: (OWNER, "dismiss the formal request for changes"),
    Route.UNREAD: (ORCHESTRATOR, UNREAD_SAID),
    Route.UNDRAFT: (ORCHESTRATOR, "`act undraft` once the Plan is approved"),
    Route.LABEL: (
        ORCHESTRATOR,
        "`act label --remove` the label pitboss does not apply",
    ),
    Route.DISARM: (ORCHESTRATOR, "`act disarm`, then `act arm`"),
    Route.BEHIND: (ORCHESTRATOR, "`act update-branch`"),
    Route.UNSTABLE: (ORCHESTRATOR, TRIAGE),
    Route.RED: (ORCHESTRATOR, TRIAGE),
    Route.MAX_LINES: (
        ORCHESTRATOR,
        "`act override` naming the ruling, or split the ticket",
    ),
    Route.TICKET: (
        ORCHESTRATOR,
        "`act close` the PR or `act pr-edit` to the open ticket",
    ),
    Route.CONFLICT: (WORKER, "merge main into the branch, `act push`"),
    Route.BODY: (WORKER, "`act pr-edit` with the body in its form"),
    Route.ADDED_LINES: (WORKER, "cut the added lines, `act push`"),
    Route.WORKFLOW: (WORKER, "cite the scratch run in the body, `act pr-edit`"),
    Route.NO_TICKET: (WORKER, "`act pr-edit`: the first line is `Fixes #N`"),
    Route.REVIEW: (REVIEWER, "`act review` the head as it is now"),
}
SHAPE_ERRORS = (AttributeError, TypeError, KeyError, ValueError)
ACTIONS = gatefacts.ACTIONS


def _found(action: str, gate: Gate, policy: gatepolicy.Policy) -> Sequence[Stop]:
    # every row's stops, in the order act ran them
    pull, ctx, state = gate.pull, {**gate.inputs, "action": action}, gate.state
    kind = totalbody.kind(pull, listed(ctx, "files"))
    change = kind == totalbody.CHANGE
    return [
        *gaterows.read_stops(ctx),
        *gaterows.field_stops(pull, ctx, policy.schema),
        *gaterows.hold_stops(action, state),
        *gaterows.check_stops(action, ctx),
        *(gaterows.review_stops(action, pull, ctx, policy) if change else ()),
        *gaterows.body_stops(pull, ctx, policy),
        *gaterows.merge_stops(action, pull, ctx),
        *gaterows.diff_stops(action, ctx, kind),
        *(gaterows.unticketed_stops(ctx) if change else ()),
        *gaterows.ticket_stops(ctx),
        *gateevents.event_stops(ctx, policy.benign),
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
    rows = policy or gatepolicy.shipped()
    ctx = {**gate.inputs, "action": action}
    if missing := gaterows.unread_stops(ctx):
        return missing
    try:
        found = _found(action, gate, rows)
    except SHAPE_ERRORS as error:  # a response out of GitHub's schema is unread
        why = f"{type(error).__name__}: {str(error)[:60]}"
        line = f"input: the response is not of GitHub's schema ({why})"
        return [Stop(route=Route.UNREAD, line=line)]
    lifted = _overridden(name_at(gate.pull, "head", "sha"), ctx)
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


def _overridden(head: str, ctx: JsonMap) -> str:
    # the override records of the head, as one text
    identity = text(ctx.get("act_identity"))
    records = totalreview.act_records(listed(ctx, "timeline"), identity, "override")
    return "\n".join(rest for at, rest in records if at == head)
