"""A stop of a merge, an arm or an undraft, and its route (keyword: gate).

Each producer of ``gaterows`` and ``gateevents`` names the route of what it finds
where it finds it; each route carries who acts on it (``Handling``).
"""

import dataclasses
import enum
from typing import Callable, Mapping, Sequence

from . import answer
from .pullrecords import Ticket, Unread

Review = Callable[[str, str, str, Mapping[str, Ticket | Unread]], str]
Plan = Callable[[str, str], str]
Body = Callable[[str, str], Sequence[str]]


UNREAD_SAID = "read the PR on GitHub and file what it answered"
TRIAGE = "triage the red: `act dispatch-next`"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Handling:
    """What a route is, who acts on it, and how.

    Attributes:
        what: what stops the action, in words (each route's own).
        actor: who acts on it; None when no actor takes it now (a hold, a run, a
            blocker, a closed PR, another queue's PR, GitHub not decided).
        said: what the actor does, empty when no actor takes it.
        lifted: whether ``act override`` may lift it (never a red, an unread
            input, or a route no actor takes).
    """

    what: str
    actor: answer.Actor | None
    said: str
    lifted: bool


OWNER = answer.Actor.OWNER
ORCHESTRATOR = answer.Actor.ORCHESTRATOR
WORKER = answer.Actor.WORKER
REVIEWER = answer.Actor.REVIEWER


def _lifted(actor: answer.Actor, what: str, said: str) -> Handling:
    # a route an actor takes, which ``act override`` may lift
    return Handling(what=what, actor=actor, said=said, lifted=True)


def _kept(actor: answer.Actor, what: str, said: str) -> Handling:
    # a route an actor takes, which no override lifts (a red, an unread input)
    return Handling(what=what, actor=actor, said=said, lifted=False)


def _untaken(what: str) -> Handling:
    # a route no actor takes now, which no override lifts
    return Handling(what=what, actor=None, said="", lifted=False)


class Route(enum.Enum):
    """Who acts on a stop, and how: each route carries its own (keyword: gate).

    Every member is made with its ``Handling``, so no route is without its actor
    and its words, and nothing looks a route up in a table.

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

    HOLD = _untaken("a hold covers the action")
    PAUSED = _lifted(OWNER, "the owner paused the PR", "remove paused-owner")
    LOCK = _lifted(OWNER, "the conversation is locked", "unlock the conversation")
    REVIEWERS = _lifted(
        OWNER,
        "a human review was requested",
        "give or withdraw the requested human review",
    )
    CHANGES_REQUESTED = _lifted(
        OWNER,
        "a human's formal request for changes stands",
        "dismiss the formal request for changes",
    )
    UNREAD = _kept(
        ORCHESTRATOR,
        "GitHub answered a read with an error, or out of its schema",
        UNREAD_SAID,
    )
    CLOSED = _untaken("the PR is closed or merged")
    FOREIGN = _untaken("not a PR of this queue")
    UNDRAFT = _lifted(
        ORCHESTRATOR, "the PR is a draft", "`act undraft` once the Plan is approved"
    )
    LABEL = _lifted(
        ORCHESTRATOR,
        "a label pitboss does not apply",
        "`act label --remove` the label pitboss does not apply",
    )
    DISARM = _lifted(
        ORCHESTRATOR,
        "auto-merge armed with no arm record for the head",
        "`act disarm`, then `act arm`",
    )
    CONFLICT = _lifted(
        WORKER,
        "the PR conflicts with its base",
        "merge main into the branch, `act push`",
    )
    BEHIND = _lifted(
        ORCHESTRATOR,
        "the base moved and there is no merge queue",
        "`act update-branch`",
    )
    UNSTABLE = _kept(ORCHESTRATOR, "a check that is not required is not green", TRIAGE)
    UNDECIDED = _untaken("GitHub has not decided whether the PR merges")
    RUNNING = _untaken("a check or status of the head has not finished")
    RED = _kept(ORCHESTRATOR, "a check or status of the head failed", TRIAGE)
    REVIEW = _lifted(
        REVIEWER,
        "the newest review is not of the head as it is",
        "`act review` the head as it is now",
    )
    BLOCKED = _untaken("an item the PR names as its blocker is open")
    BODY = _lifted(
        WORKER,
        "the body breaks one of its rows",
        "`act pr-edit` with the body in its form",
    )
    ADDED_LINES = _lifted(
        WORKER, "a .md or .rst file gets added lines", "cut the added lines, `act push`"
    )
    MAX_LINES = _lifted(
        ORCHESTRATOR,
        "the diff is over the ticket's Max-lines",
        "`act override` naming the ruling, or split the ticket",
    )
    WORKFLOW = _lifted(
        WORKER,
        "a workflow file changed with no green text-lint",
        "cite the scratch run in the body, `act pr-edit`",
    )
    NO_TICKET = _lifted(
        WORKER,
        "the body closes no ticket",
        "`act pr-edit`: the first line is `Fixes #N`",
    )
    TICKET = _lifted(
        ORCHESTRATOR,
        "a ticket the body closes is not an open issue",
        "`act close` the PR or `act pr-edit` to the open ticket",
    )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Stop:
    """One reason the action may not be taken now.

    Attributes:
        route: who acts on it.
        line: what it is, in one line (an override names it).
    """

    route: Route
    line: str
