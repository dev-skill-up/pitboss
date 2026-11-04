"""A PR that closes more than one ticket (keyword: fold, pitboss#171).

A rule that caps the open PRs is met by finishing or closing PRs, never by
folding several tickets into one. A body whose ``Fixes`` and ``Closes`` lines
name more than one ticket is refused unless it cites an Opus ruling comment of
that PR (its address) whose ``Ruling:`` line is ``do these steps``.
"""

import json
import re
from typing import AbstractSet, Sequence

from . import flowstate, parsing, rulingwords, shapes

CLOSING = re.compile(r"\b(?:Fixes|Closes)\s+((?:[\w.-]+/[\w.-]+)?#\d+)", re.IGNORECASE)
# the comment's address, then its text
Recorded = tuple[str, str]


def tickets(body: str) -> Sequence[str]:
    """The tickets a body says it fixes or closes.

    Args:
        body: the PR body.

    Returns:
        Each ticket once, upper-cased and sorted.
    """
    return sorted({each.upper() for each in CLOSING.findall(body)})


def cites(body: str, url: str) -> bool:
    """Whether a body holds a comment's address, whole.

    Args:
        body: the PR body.
        url: the comment's address.

    Returns:
        True when the address is in the body and no word character follows
        it (``#issuecomment-1`` is not cited by ``#issuecomment-12``).
    """
    return re.search(re.escape(url) + r"(?!\w)", body) is not None


def allows(body: str, rulings: Sequence[Recorded]) -> bool:
    """Whether the body cites an Opus ruling that allows several tickets.

    Args:
        body: the PR body.
        rulings: each recorded comment of the PR, its address and its text.

    Returns:
        True when the body holds the address of a comment that is an Opus
        ruling whose ruling is ``do these steps``.
    """
    return any(
        cites(body, url)
        and flowstate.read_ruling(text) is rulingwords.Ruling.DO_THESE_STEPS
        for url, text in rulings
        if url
    )


def ruling_comments(
    comments: Sequence[shapes.Comment], trusted: AbstractSet[str]
) -> Sequence[Recorded]:
    """The Opus ruling comments of trusted authors.

    Args:
        comments: the comments of a PR.
        trusted: the author associations whose comments count.

    Returns:
        The address and text of each.
    """
    return [
        (each.url, each.body)
        for each in comments
        if flowstate.is_ruling(each.body) and each.author_association in trusted
    ]


def _comment_objects(value: object) -> list[object]:
    if isinstance(value, list):
        return [each for item in value for each in _comment_objects(item)]
    return [value]


def read_comments(text: str, trusted: AbstractSet[str]) -> Sequence[Recorded]:
    """The Opus ruling comments in the API's list of a PR's comments.

    ``gh api --paginate`` prints one JSON list for each page, one after
    another, and ``--slurp`` wraps the pages in one more list; both are read.

    Args:
        text: the response of ``issues/<number>/comments``, all its pages.
        trusted: the author associations whose comments count.

    Returns:
        The address and text of each ruling comment of a trusted author.

    Raises:
        ValueError: the text is not the comments of a PR.
    """
    decoder = json.JSONDecoder()
    rest = text.strip()
    objects: list[object] = []
    while rest:
        page, end = decoder.raw_decode(rest)
        objects.extend(_comment_objects(page))
        rest = rest[end:].lstrip()
    if not all(isinstance(each, dict) for each in objects):
        raise ValueError("a comment is not an object")
    try:
        return ruling_comments(parsing.comments(json.dumps(objects)), trusted)
    except KeyError as error:
        raise ValueError(f"a comment has no {error}") from error


def message(named: Sequence[str]) -> str:
    """The finding for a body that closes several tickets.

    Args:
        named: the tickets.

    Returns:
        The finding's text.
    """
    return (
        f"Fixes and Closes name {len(named)} tickets ({', '.join(named)}): one"
        " ticket, one PR; a dependency is its own ticket and PR; several need"
        " an Opus ruling comment (Ruling: do these steps) of this PR, cited by"
        " its address, recorded before the first push"
    )


def folded(body: str, rulings: Sequence[Recorded]) -> Sequence[str]:
    """The tickets of a body that closes several without an allowing ruling.

    Args:
        body: the PR body.
        rulings: each recorded comment of the PR, its address and its text.

    Returns:
        The tickets, none when the body names one or cites a ruling.
    """
    named = tickets(body)
    return named if len(named) > 1 and not allows(body, rulings) else []
