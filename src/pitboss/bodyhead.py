"""The body of a PR after a merge of the base: its new ``Head:`` line (pitboss#369).

(Keyword: body-head.) ``text-lint`` reads the last ``Head: <40 hex>`` line of a
PR body as the head the body describes, so a merge of main into the branch
needs exactly one change to the body: a new ``Head:`` line, after the last one.
The module reads no file and calls nothing.
"""

import dataclasses
import re

from . import bodydigest, ghapi, ghstore, parsing
from .running import Run

LINE = re.compile(r"Head: ([0-9a-f]{40})")
ENDING = "\r\n"


def last_head(body: str) -> str:
    """The head the last ``Head:`` line of a body names.

    Args:
        body: the PR body.

    Returns:
        The 40 hex digits; empty when the body has no such line.
    """
    found = [LINE.fullmatch(each.rstrip()) for each in body.splitlines()]
    heads = [each.group(1) for each in found if each]
    return heads[-1] if heads else ""


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


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Moved:
    """What the move of a PR's body to its head gave.

    Attributes:
        old: the head the body named before.
        new: the head now.
        digest: the digest of the new body.
    """

    old: str
    new: str
    digest: str


def _api(read: Run, write: Run) -> ghapi.GitHub:
    return ghapi.GitHub(run=read, mutate=write)


def move(read: Run, write: Run, path: str) -> Moved | None:
    """Put the PR's head in its body (only when not a dry run).

    Args:
        read: the runner reads go through.
        write: the runner changes go through (a dry run unless asked).
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
    found = Moved(old=old, new=pull.head.sha, digest=bodydigest.digest(new))
    return found if old else None
