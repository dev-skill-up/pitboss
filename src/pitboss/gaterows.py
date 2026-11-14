"""The stops of a merge, an arm or an undraft, each with its route (keyword: gate).

The rows the act verdict ran (pitboss#444) are rows of ``decide`` now (the one-path
plan, P8): each producer here names the route of what it finds where it finds it, so
no line is classified afterwards. The rows read the typed state ``pullstate`` made
(plan 6.1); nothing here reads, and nothing here reads JSON.
"""

from typing import Protocol, Sequence

from . import totalbody, totalchecks
from .gatestop import Body, Plan, Review, Route, Stop
from .pullrecords import Event, GateState, Mistyped, Ticket, Unread, listed
from .totalanswer import GATED_ACTIONS, MERGE_ACTIONS, PAUSED

CHANGES_REQUESTED = ("changes_requested", "CHANGES_REQUESTED")


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


def unread_stops(state: GateState) -> Sequence[Stop]:
    """The inputs that were not given: no input has a default.

    Args:
        state: the typed state.

    Returns:
        A stop for each input absent.
    """
    return [
        Stop(route=Route.UNREAD, line=f"input {key}: not read (no input has a default)")
        for key in state.absent
    ]


def _reads(state: GateState) -> Sequence[tuple[str, object]]:
    reads = state.reads
    return [
        ("check_runs", reads.runs),
        ("statuses", reads.statuses),
        ("files", reads.files),
        ("timeline", reads.timeline),
    ]


def schema_stops(state: GateState) -> Sequence[Stop]:
    """The read lists that are not of GitHub's schema: one stop, the first.

    Args:
        state: the typed state.

    Returns:
        One stop when a list holds a member of another shape than documented.
    """
    for key, read in _reads(state):
        if isinstance(read, Mistyped):
            why = f"{key}: {read.name}={read.said}"
            line = f"input: the response is not of GitHub's schema ({why})"
            return [Stop(route=Route.UNREAD, line=line)]
    return []


def read_stops(state: GateState) -> Sequence[Stop]:
    """The inputs GitHub answered with an error.

    Args:
        state: the typed state.

    Returns:
        A stop for each.
    """
    return [
        Stop(route=Route.UNREAD, line=f"input {key}: GitHub answered {read.why[:60]}")
        for key, read in _reads(state)
        if isinstance(read, Unread)
    ]


def check_stops(action: str, state: GateState) -> Sequence[Stop]:
    """The stops of the head's check runs and statuses.

    Args:
        action: the action.
        state: the typed state.

    Returns:
        A stop for each failed or unreported one, and each one still running.
    """
    runs, statuses = listed(state.reads.runs), listed(state.reads.statuses)
    required = state.repository.required_checks
    return [
        Stop(route=Route.RUNNING if running else Route.RED, line=line)
        for line, running in totalchecks.check_stops(action, runs, statuses, required)
    ]


def hold_stops(action: str, state: GateState) -> Sequence[Stop]:
    """The stops of the holds that cover the action.

    Args:
        action: the action.
        state: the typed state.

    Returns:
        A stop for each.
    """
    lines = totalchecks.hold_lines(action, state.holds)
    return [Stop(route=Route.HOLD, line=each) for each in lines]


def review_stops(action: str, state: GateState, policy: Readings) -> Sequence[Stop]:
    """The stops of the newest review: it binds the head, the body and the tickets.

    Args:
        action: the action.
        state: the typed state.
        policy: the readings of a review.

    Returns:
        One stop when the newest review does not approve what the action needs.
    """
    attempts = state.attempts
    newest = attempts[-1].body if attempts else ""
    body = state.pull.body
    if action in MERGE_ACTIONS:
        head = state.pull.where.head_sha
        why = policy.review(newest, head, body, state.tickets)
    elif action == "undraft":
        why = policy.plan(newest, body)
    else:
        return []
    said = why if attempts else "no review attempt on this PR"
    return [Stop(route=Route.REVIEW, line=f"review: {said}")] if said else []


def body_stops(state: GateState, policy: Readings) -> Sequence[Stop]:
    """The stops of the body's rows (an open blocker is the decision's: plan 6.1).

    Args:
        state: the typed state.
        policy: the reading of a body.

    Returns:
        A stop for each row the body breaks.
    """
    head = state.pull.where.head_sha
    return [
        Stop(route=Route.BODY, line=each) for each in policy.body(state.pull.body, head)
    ]


def diff_stops(action: str, state: GateState, kind: str) -> Sequence[Stop]:
    """The stops of the diff.

    Args:
        action: the action.
        state: the typed state.
        kind: the PR's kind.

    Returns:
        A stop for added lines of a .md or .rst file, a diff over its Max-lines
        and a workflow file with no green text-lint.
    """
    files = listed(state.reads.files)
    found = []
    if action in GATED_ACTIONS:
        lines = totalchecks.markup_lines(files)
        found += [Stop(route=Route.ADDED_LINES, line=each) for each in lines]
    if action in MERGE_ACTIONS:
        most = state.repository.max_lines
        size = totalchecks.size_lines(kind, files, most)
        found += [Stop(route=Route.MAX_LINES, line=each) for each in size]
        statuses = listed(state.reads.statuses)
        flows = totalchecks.workflow_lines(files, statuses)
        found += [Stop(route=Route.WORKFLOW, line=each) for each in flows]
    return found


def _changes_requested(timeline: Sequence[Event]) -> bool:
    return any(
        each.kind == "reviewed" and each.state in CHANGES_REQUESTED for each in timeline
    )


def merge_stops(action: str, state: GateState) -> Sequence[Stop]:
    """The stops only a merge or an arm has.

    Args:
        action: the action.
        state: the typed state.

    Returns:
        A stop for a standing formal request for changes, and for auto-merge armed
        on a paused PR.
    """
    if action not in MERGE_ACTIONS:
        return []
    found = []
    if _changes_requested(listed(state.reads.timeline)):
        line = "review: a formal request for changes stands"
        found.append(Stop(route=Route.CHANGES_REQUESTED, line=line))
    merging = state.pull.merging
    if PAUSED in merging.labels and merging.auto_merge:
        line = "auto_merge armed on a paused-owner PR: only disarm is allowed"
        found.append(Stop(route=Route.PAUSED, line=line))
    return found


def unticketed_stops(state: GateState) -> Sequence[Stop]:
    """The stop of a change whose body closes no ticket.

    Args:
        state: the typed state.

    Returns:
        One stop when the body closes none.
    """
    if state.tickets:
        return []
    return [Stop(route=Route.NO_TICKET, line="ticket: the body closes no ticket")]


def _ticket_line(ref: str, read: Ticket | Unread) -> str:
    # the stop line of one ticket the body closes, "" for an open issue unlocked
    if isinstance(read, Unread):
        return f"ticket {ref}: not read ({read.why[:40]})"
    if read.is_pull:
        return f"ticket {ref}: a pull request, not an issue"
    if read.state != "open":
        return f"ticket {ref}: {read.state} ({read.reason})"
    return f"ticket {ref}: locked" if read.locked else ""


def ticket_stops(state: GateState) -> Sequence[Stop]:
    """The stops of the tickets the body closes.

    Args:
        state: the typed state.

    Returns:
        A stop for each that is no open issue.
    """
    return [
        Stop(route=Route.TICKET, line=line)
        for ref, read in state.tickets.items()
        if (line := _ticket_line(ref, read))
    ]


def kind_of(state: GateState) -> str:
    """The PR's kind, by its head branch and its files.

    Args:
        state: the typed state.

    Returns:
        ``relock``, ``publish`` or ``change``.
    """
    names = [each.name for each in listed(state.reads.files)]
    return totalbody.kind(state.pull.where.head_ref, names)
