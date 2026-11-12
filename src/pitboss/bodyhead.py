"""The body of a PR after a merge of the base: its new ``Head:`` line (pitboss#369).

(Keyword: body-head.) ``text-lint`` reads the last ``Head: <40 hex>`` line of a
PR body as the head the body describes, so a merge of main into the branch
needs exactly one change to the body: a new ``Head:`` line, after the last one.
The module reads no file and calls nothing.
"""

import dataclasses
import re
from typing import Sequence

from . import bodydigest, ghapi, ghstore, headline, parsing, shapes
from .running import Run

LINE = headline.LINE
ENDING = "\r\n"


last_head = headline.last_head


def with_head(body: str, head: str) -> str:
    """The body with a ``Head:`` line for ``head`` after its last ``Head:`` line.

    Nothing else changes: the line ending of that line is the new line's, and a
    body whose last ``Head:`` line already names ``head`` is returned as it is.

    Args:
        body: the PR body, which has a ``Head:`` line.
        head: the new head (40 hex digits).

    Returns:
        The new body.
    """
    lines = body.splitlines(keepends=True)
    at = max(index for index, each in enumerate(lines) if LINE.fullmatch(each.rstrip()))
    if last_head(body) == head:
        return body
    old = lines[at]
    ending = old[len(old.rstrip(ENDING)) :]
    new = f"Head: {head}"
    lines[at] = f"{old}{new}{ending}" if ending else f"{old}\n{new}"
    return "".join(lines)


TRUSTED = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
APPROVAL = re.compile(r"(?m)^Verdict: approved$")
REVIEWED = re.compile(r"(?m)^Reviewed: ([0-9a-f]{40})$")


def approved_head(comments: Sequence[shapes.Comment]) -> str:
    """The head the newest approving review of a PR names (keyword: merge-proof).

    ``pwa/CLAUDE.md`` names the reviewed SHA as the first argument of ``bats
    merge-proof``, not the body's last ``Head:`` line (pitboss#394): a PR merged
    with main twice has moved its body's head past the review.

    Args:
        comments: the PR's issue comments.

    Returns:
        The ``Reviewed:`` SHA of the newest review comment by a trusted author
        that says ``Verdict: approved``; empty when no review does.
    """
    reviews = [
        (each.created_at, REVIEWED.search(each.body))
        for each in comments
        if each.author_association in TRUSTED and APPROVAL.search(each.body)
    ]
    named = [(when, found.group(1)) for when, found in reviews if found]
    return max(named, default=("", ""))[1]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Moved:
    """What the move of a PR's body to its head gave.

    Attributes:
        old: the head the body named before.
        new: the head now.
        digest: the digest of the new body.
        reviewed: the head the newest approving review names, empty when none
            does (pitboss#394).
    """

    old: str
    new: str
    digest: str
    reviewed: str = ""


def _api(read: Run, write: Run) -> ghapi.GitHub:
    return ghapi.GitHub(run=read, mutate=write)


def move(read: Run, write: Run, path: str) -> Moved | None:
    """Put the PR's head in its body.

    Args:
        read: the runner reads go through.
        write: the runner changes go through.
        path: the pull request's path.

    Returns:
        What it gave; None when the body has no ``Head:`` line.
    """
    github = _api(read, write)
    pull = parsing.pull(ghapi.get(github, path))
    old = last_head(pull.body)
    new = with_head(pull.body, pull.head.sha) if old else pull.body
    if old and new != pull.body:
        ghstore.set_body(github, path, new)
    posted = ghapi.pages(
        github, path.replace("/pulls/", "/issues/") + "/comments", parsing.comments
    )
    found = Moved(
        old=old,
        new=pull.head.sha,
        digest=bodydigest.digest(new),
        reviewed=approved_head(posted),
    )
    return found if old else None
