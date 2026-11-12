"""Cases and the Done-when are posted into the ticket's body, never a comment.

Owner, 2026-11-08T23:06Z: "NOT ADDING STUFF IN COMMENTS, ONLY BY EDITING THE BODY,
AND ONLY BEFORE A WORKER HAS STARTED" (A19), and a PR a worker started gets nothing
added, new findings going to an older open ticket (A31, owner 2026-11-08 21:02Z).
``pitboss case post`` edits the body with these functions (keyword: case-post,
pitboss#444). The module reads nothing: the texts are given.
"""

from typing import Sequence

from . import config, fixnames, ledger, ticketwhen

STARTED = (
    "PR {pull} says it fixes {ticket}, so a worker started: the body is edited only"
    " before a worker starts; file the new finding on an older open ticket"
)


def started_by(ticket: str, pulls: Sequence[tuple[int, str]], repo: config.Repo) -> int:
    """The first PR whose body says it fixes the ticket.

    Args:
        ticket: the ticket in full, ``owner/name#N``.
        pulls: each PR's number and body.
        repo: the ticket's repository, the owner of a bare ``Fixes #N``.

    Returns:
        The PR's number; 0 when no PR fixes the ticket (no worker started).
    """
    for number, body in pulls:
        named = [ledger.reference(each, repo) for each in fixnames.FIXES.findall(body)]
        if ticket in named:
            return number
    return 0


def refusal(ticket: str, started: int) -> str:
    """Say why the ticket's body may not be edited.

    Args:
        ticket: the ticket in full.
        started: ``started_by``'s answer.

    Returns:
        The reason; an empty string when no worker started.
    """
    return STARTED.format(pull=f"#{started}", ticket=ticket) if started else ""


def with_done_when(body: str, text: str) -> str:
    """The ticket body with its Done-when section replaced.

    Args:
        body: the ticket's body.
        text: the new Done-when.

    Returns:
        The body whose Done-when section is the text, its heading kept; a body
        with none gets a ``## Done when`` section at its end.
    """
    found = ticketwhen.SECTION.search(body)
    new = text.strip("\n") + "\n\n"
    if found is None:
        return body.rstrip("\n") + "\n\n## Done when\n\n" + new
    return body[: found.start(2)] + "\n" + new + body[found.end(2) :]


def with_case(body: str, text: str) -> str:
    """The ticket body with a case added at its end.

    Args:
        body: the ticket's body.
        text: the case.

    Returns:
        The body, a blank line, the case.
    """
    return body.rstrip("\n") + "\n\n" + text.strip("\n") + "\n"
