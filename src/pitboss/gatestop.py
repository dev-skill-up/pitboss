"""A stop of a merge, an arm or an undraft, and its route (keyword: gate).

Each producer of ``gaterows`` and ``gateevents`` names the route of what it finds
where it finds it; ``gate.ROUTES`` says who acts on each.
"""

import dataclasses
import enum
from typing import Callable, Mapping, Sequence

Review = Callable[[str, str, object, Mapping[str, object]], str]
Plan = Callable[[str, object], str]
Body = Callable[[object, str], Sequence[str]]


class Route(enum.Enum):
    """Who acts on a stop, and how.

    Attributes:
        HOLD: a hold covers the action.
        PAUSED: the owner paused the PR.
        LOCK: the conversation is locked.
        REVIEWERS: a human review was requested.
        CHANGES_REQUESTED: a human's formal request for changes stands.
        UNREAD: GitHub answered a read with an error, or out of its schema.
        CLOSED: the PR is closed or merged.
        FOREIGN: not a PR of this queue.
        UNDRAFT: the PR is a draft.
        LABEL: a label pitboss does not apply.
        DISARM: auto-merge armed with no arm record for the head.
        CONFLICT: the PR conflicts with its base.
        BEHIND: the base moved and there is no merge queue.
        UNSTABLE: a check that is not required is not green.
        UNDECIDED: GitHub has not decided whether the PR merges.
        RUNNING: a check or status of the head has not finished.
        RED: a check or status of the head failed.
        REVIEW: the newest review is not of the head as it is.
        BLOCKED: an item the PR names as its blocker is open.
        BODY: the body breaks one of its rows.
        ADDED_LINES: a .md or .rst file gets added lines.
        MAX_LINES: the diff is over the ticket's Max-lines.
        WORKFLOW: a workflow file changed with no green text-lint.
        NO_TICKET: the body closes no ticket.
        TICKET: a ticket the body closes is not an open issue.
    """

    HOLD = enum.auto()
    PAUSED = enum.auto()
    LOCK = enum.auto()
    REVIEWERS = enum.auto()
    CHANGES_REQUESTED = enum.auto()
    UNREAD = enum.auto()
    CLOSED = enum.auto()
    FOREIGN = enum.auto()
    UNDRAFT = enum.auto()
    LABEL = enum.auto()
    DISARM = enum.auto()
    CONFLICT = enum.auto()
    BEHIND = enum.auto()
    UNSTABLE = enum.auto()
    UNDECIDED = enum.auto()
    RUNNING = enum.auto()
    RED = enum.auto()
    REVIEW = enum.auto()
    BLOCKED = enum.auto()
    BODY = enum.auto()
    ADDED_LINES = enum.auto()
    MAX_LINES = enum.auto()
    WORKFLOW = enum.auto()
    NO_TICKET = enum.auto()
    TICKET = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Stop:
    """One reason the action may not be taken now.

    Attributes:
        route: who acts on it.
        line: what it is, in one line (an override names it).
    """

    route: Route
    line: str
