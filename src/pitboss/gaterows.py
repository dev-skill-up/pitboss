"""The stops of a merge, an arm or an undraft, each with its route (keyword: gate).

The rows the act verdict ran (pitboss#444) are rows of ``decide`` now (the one-path
plan, P8): each producer here names the route of what it finds where it finds it, so
no line is classified afterwards. The facts are the PR as GitHub answered and the
inputs read with it (``gateread``); nothing here reads.
"""

from typing import Callable, Mapping, Protocol, Sequence

from . import totalchecks, totalreview, totalrows, totalschema
from .gatestop import Body, Plan, Review, Route, Stop
from .totalanswer import GATED_ACTIONS, MERGE_ACTIONS, PAUSED
from .totaljson import JsonMap, failed_read, listed, members, name_at, records, text

REQUIRED = (
    "repo",
    "number",
    "default_branch",
    "authors",
    "act_identity",
    "required_checks",
    "merge_queue",
    "check_runs",
    "statuses",
    "tickets",
    "files",
    "max_lines",
    "holds",
    "timeline",
    "blockers",
)


class Readings(Protocol):
    """The readings of a review and a body the rows run (``gatepolicy.Policy``)."""

    @property
    def review(self) -> Review:
        """Why the newest review does not approve.

        Returns:
            The reading.
        """

    @property
    def plan(self) -> Plan:
        """Why the newest review does not approve the Plan.

        Returns:
            The reading.
        """

    @property
    def body(self) -> Body:
        """The body's own stop lines.

        Returns:
            The reading.
        """


READS = ("check_runs", "statuses", "files", "timeline")
CHANGES_REQUESTED = ("changes_requested", "CHANGES_REQUESTED")
CLOSED_FIELDS = frozenset({"state", "merged", "merged_at", "merged_by", "closed_at"})
FOREIGN_FIELDS = frozenset(
    {"number", "url", "base", "head", "user", "author_association"}
)
FIELD_ROUTES: Mapping[str, Route] = {
    "draft": Route.UNDRAFT,
    "auto_merge": Route.DISARM,
    "mergeable": Route.UNDECIDED,
    "locked": Route.LOCK,
    "active_lock_reason": Route.LOCK,
    "requested_reviewers": Route.REVIEWERS,
    "requested_teams": Route.REVIEWERS,
    **{name: Route.CLOSED for name in CLOSED_FIELDS},
    **{name: Route.FOREIGN for name in FOREIGN_FIELDS},
    **{name: Route.FOREIGN for name in totalrows.URL_FIELDS},
}
MERGEABLE_ROUTES: Mapping[str, Route] = {
    "dirty": Route.CONFLICT,
    "behind": Route.BEHIND,
    "unstable": Route.UNSTABLE,
    "draft": Route.UNDRAFT,
}


def _label_route(pull: JsonMap) -> Route:
    labelled = [text(each.get("name")) for each in records(pull.get("labels"))]
    return Route.PAUSED if PAUSED in labelled else Route.LABEL


def _merge_route(pull: JsonMap) -> Route:
    return MERGEABLE_ROUTES.get(text(pull.get("mergeable_state")), Route.UNDECIDED)


VALUE_ROUTES: Mapping[str, Callable[[JsonMap], Route]] = {
    "labels": _label_route,
    "mergeable_state": _merge_route,
}


def _field_route(name: str, pull: JsonMap) -> Route:
    reader = VALUE_ROUTES.get(name)
    return reader(pull) if reader else FIELD_ROUTES.get(name, Route.UNREAD)


def field_stops(
    pull: JsonMap, ctx: JsonMap, schema: Mapping[str, str]
) -> Sequence[Stop]:
    """The stops of the PR's own fields, one row for each documented field.

    Args:
        pull: the PR as GitHub answered.
        ctx: the inputs, with ``action``.
        schema: each field's declaration.

    Returns:
        A stop for each field whose row fails, and each required field absent.
    """
    found = []
    for name, row in totalrows.rows(schema).items():
        value = pull.get(name)
        ok, why = row(value, pull, ctx)
        if ok and name in pull and not totalschema.typed(value, schema.get(name, "")):
            ok, why = False, "not of the documented type"
        if not ok:
            route = _field_route(name, pull)
            found.append(Stop(route=route, line=f"{name}={str(value)[:50]}: {why}"))
    found += [
        Stop(route=Route.UNREAD, line=f"{name}: a required field is absent")
        for name, declaration in schema.items()
        if totalschema.required(declaration) and name not in pull
    ]
    return found


def unread_stops(ctx: JsonMap) -> Sequence[Stop]:
    """The inputs that were not read: no input has a default.

    Args:
        ctx: the inputs.

    Returns:
        A stop for each required input absent.
    """
    return [
        Stop(route=Route.UNREAD, line=f"input {key}: not read (no input has a default)")
        for key in REQUIRED
        if key not in ctx
    ]


def read_stops(ctx: JsonMap) -> Sequence[Stop]:
    """The inputs GitHub answered with an error.

    Args:
        ctx: the inputs.

    Returns:
        A stop for each.
    """
    return [
        Stop(route=Route.UNREAD, line=f"input {key}: GitHub answered {why[:60]}")
        for key in READS
        if (why := failed_read(ctx.get(key)))
    ]


def check_stops(action: str, ctx: JsonMap) -> Sequence[Stop]:
    """The stops of the head's check runs and statuses.

    Args:
        action: the action.
        ctx: the inputs.

    Returns:
        A stop for each failed or unreported one, and each one still running.
    """
    return [
        Stop(route=Route.RUNNING if running else Route.RED, line=line)
        for line, running in totalchecks.check_stops(action, ctx)
    ]


def hold_stops(action: str, ctx: JsonMap) -> Sequence[Stop]:
    """The stops of the holds that cover the action.

    Args:
        action: the action.
        ctx: the inputs, with ``holds``.

    Returns:
        A stop for each.
    """
    lines = totalchecks.hold_lines(action, listed(ctx, "holds"))
    return [Stop(route=Route.HOLD, line=each) for each in lines]


def review_stops(
    action: str, pull: JsonMap, ctx: JsonMap, policy: Readings
) -> Sequence[Stop]:
    """The stops of the newest review: it binds the head, the body and the tickets.

    Args:
        action: the action.
        pull: the PR.
        ctx: the inputs.
        policy: the readings of a review.

    Returns:
        One stop when the newest review does not approve what the action needs.
    """
    attempts = totalreview.review_attempts(listed(ctx, "timeline"))
    newest = text(attempts[-1].get("body")) if attempts else ""
    if action in MERGE_ACTIONS:
        head = name_at(pull, "head", "sha")
        tickets = members(ctx.get("tickets"))
        why = policy.review(newest, head, pull.get("body"), tickets)
    elif action == "undraft":
        why = policy.plan(newest, pull.get("body"))
    else:
        return []
    said = why if attempts else "no review attempt on this PR"
    return [Stop(route=Route.REVIEW, line=f"review: {said}")] if said else []


def body_stops(pull: JsonMap, ctx: JsonMap, policy: Readings) -> Sequence[Stop]:
    """The stops of the body's rows and of the block records.

    Args:
        pull: the PR.
        ctx: the inputs.
        policy: the reading of a body.

    Returns:
        A stop for each row the body breaks, and each open blocker.
    """
    blockers = members(ctx.get("blockers"))
    head = name_at(pull, "head", "sha")
    found = [
        Stop(route=Route.BODY, line=each)
        for each in policy.body(pull.get("body"), head)
    ]
    found += [
        Stop(route=Route.BLOCKED, line=f"blocked: {ref}, which is {state}")
        for ref, state in blockers.items()
        if state != "closed"
    ]
    return found


def diff_stops(action: str, ctx: JsonMap, kind: str) -> Sequence[Stop]:
    """The stops of the diff.

    Args:
        action: the action.
        ctx: the inputs.
        kind: the PR's kind.

    Returns:
        A stop for added lines of a .md or .rst file, a diff over its Max-lines
        and a workflow file with no green text-lint.
    """
    files = listed(ctx, "files")
    found = []
    if action in GATED_ACTIONS:
        lines = totalchecks.markup_lines(files)
        found += [Stop(route=Route.ADDED_LINES, line=each) for each in lines]
    if action in MERGE_ACTIONS:
        size = totalchecks.size_lines(kind, files, ctx.get("max_lines"))
        found += [Stop(route=Route.MAX_LINES, line=each) for each in size]
        flows = totalchecks.workflow_lines(files, listed(ctx, "statuses"))
        found += [Stop(route=Route.WORKFLOW, line=each) for each in flows]
    return found


def merge_stops(action: str, pull: JsonMap, ctx: JsonMap) -> Sequence[Stop]:
    """The stops only a merge or an arm has.

    Args:
        action: the action.
        pull: the PR.
        ctx: the inputs.

    Returns:
        A stop for a standing formal request for changes, and for auto-merge armed
        on a paused PR.
    """
    if action not in MERGE_ACTIONS:
        return []
    found = []
    if any(
        each.get("event") == "reviewed" and each.get("state") in CHANGES_REQUESTED
        for each in listed(ctx, "timeline")
    ):
        line = "review: a formal request for changes stands"
        found.append(Stop(route=Route.CHANGES_REQUESTED, line=line))
    labels = [name_at(each, "name") for each in records(pull.get("labels"))]
    if PAUSED in labels and pull.get("auto_merge"):
        line = "auto_merge armed on a paused-owner PR: only disarm is allowed"
        found.append(Stop(route=Route.PAUSED, line=line))
    return found


def unticketed_stops(ctx: JsonMap) -> Sequence[Stop]:
    """The stop of a change whose body closes no ticket.

    Args:
        ctx: the inputs.

    Returns:
        One stop when the body closes none.
    """
    if members(ctx.get("tickets")):
        return []
    return [Stop(route=Route.NO_TICKET, line="ticket: the body closes no ticket")]


def ticket_stops(ctx: JsonMap) -> Sequence[Stop]:
    """The stops of the tickets the body closes.

    Args:
        ctx: the inputs.

    Returns:
        A stop for each that is no open issue.
    """
    return [
        Stop(route=Route.TICKET, line=line)
        for ref, value in members(ctx.get("tickets")).items()
        if (line := totalrows.ticket_state(ref, value))
    ]
