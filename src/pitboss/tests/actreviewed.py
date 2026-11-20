"""A PR the gate lets merge: ``act review`` approved it (keyword: gate).

The worlds review a PR with comments in the old form, which moves the flow to the
merge step; the merge decision is the gate's (the one-path plan, P8), and the gate
reads the review ``act review`` writes in the PR's timeline and the ticket the body
closes. ``approve`` adds both, as GitHub would hold them.
"""

from typing import Mapping, MutableMapping

from .. import actwrite
from . import fakes, world

IDENTITY = "pitboss-bot"
APPROVED = ["approved", "approved", "approved"]
# the merge decision of PR {number}
MERGING = "ORCHESTRATOR: owner/project#{number}: CI is green and there is no conflict"
# the gate's decision at the merge step of a PR with no ``act review`` record
TO_REVIEW = "`act review` the head as it is now"


def _pull(here: world.World, number: int) -> MutableMapping[str, object]:
    # the PR's details, as the world cans them
    found = here.bodies[f"{world.PROJECT}/pulls/{number}"]
    assert isinstance(found, dict)
    return found


def listed_body(here: world.World, number: int, body: object) -> None:
    """Give a PR's row of the open listing a body, as GitHub's carries the PR's.

    Args:
        here: the world.
        number: the PR.
        body: its body.
    """
    fakes.listed_row(here.bodies, world.PROJECT, number, body=body)


def approve(here: world.World, number: int, ticket: int = 9) -> None:
    """Make a PR of the project close a ticket and carry an ``act review`` approval.

    Args:
        here: the world.
        number: the PR.
        ticket: the open ticket of the project its body closes.
    """
    pull = _pull(here, number)
    body = str(pull.get("body") or "")
    if not body.startswith("Fixes #"):
        body = f"Fixes #{ticket}\n\n{body}"
    pull["body"] = body
    listed_body(here, number, body)
    issue = here.bodies.get(f"{world.PROJECT}/issues/{ticket}", world.TICKET)
    assert isinstance(issue, Mapping)
    here.bodies[f"{world.PROJECT}/issues/{ticket}"] = issue
    closed = {f"owner/project#{ticket}": issue}
    review = actwrite.review_text(pull, APPROVED, "fine", closed)
    event = {
        "event": "commented",
        "user": {"login": IDENTITY},
        "body": review,
        "created_at": "2030-01-01T00:00:00Z",
    }
    _post(here, number, event)


def _post(here: world.World, number: int, event: Mapping[str, object]) -> None:
    # the review is on the PR's timeline and among its comments, which the
    # gate reads (plan 6.1)
    pages = [f"{world.PROJECT}/issues/{number}/{each}" for each in ("timeline",)]
    here.bodies[fakes.page(pages[0])] = [event]
    comments = fakes.page(f"{world.PROJECT}/issues/{number}/comments")
    found = here.bodies.get(comments)
    kept = list(found) if isinstance(found, list) else []
    here.bodies[comments] = [*kept, {**event, "author_association": "MEMBER"}]
