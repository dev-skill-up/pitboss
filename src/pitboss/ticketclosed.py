"""The tickets a name refers to, and whether one is closed (keyword: ticket-closed).

A worktree is named for its ticket (``pb-316``, ``q1079c``, ``fix-326``). When
its branch has no PR to say the work is finished, a number in its name or its
branch that is a closed ticket of its repository says it (pitboss#348).
"""

import json
import pathlib
import re
import subprocess
from typing import AbstractSet, Iterable, Sequence

from . import ghapi

NUMBER = re.compile(r"(?<!\d)\d{2,7}(?!\d)")


def numbers_in(names: Iterable[str]) -> Sequence[int]:
    """The ticket numbers in some names: runs of 2 to 7 digits, each once.

    Args:
        names: the names (a directory's, a branch's).

    Returns:
        The numbers, in the order they are first met.
    """
    found = (int(number) for name in names for number in NUMBER.findall(name))
    return list(dict.fromkeys(found))


def is_closed(github: ghapi.GitHub, slug: str, number: int) -> bool:
    """Whether a ticket (or a PR) of a repository is closed.

    Args:
        github: the API.
        slug: the repository's ``owner/name``.
        number: the number.

    Returns:
        True when GitHub says it is closed; False when it is open or cannot be
        read (no number is taken for a closed ticket on a guess).
    """
    try:
        item = dict(json.loads(ghapi.get(github, f"repos/{slug}/issues/{number}")))
    except subprocess.CalledProcessError:
        return False
    return item.get("state") == "closed"


def closed_ticket(github: ghapi.GitHub, slug: str, names: Iterable[str]) -> int:
    """The first number in some names that is a closed ticket.

    Args:
        github: the API.
        slug: the repository's ``owner/name``.
        names: the names.

    Returns:
        The number, or 0 when none is a closed ticket.
    """
    wanted = (number for number in numbers_in(names) if is_closed(github, slug, number))
    return next(wanted, 0)


def where(
    workspace: pathlib.Path, checkouts: Iterable[pathlib.Path]
) -> tuple[AbstractSet[pathlib.Path], Sequence[int]]:
    """The directories under the workspace that hold some checkouts, and their tickets.

    Args:
        workspace: the workspace.
        checkouts: the checkouts.

    Returns:
        The directories they are in, and the numbers in their names.
    """
    found = list(checkouts)
    inside = workspace.resolve()
    places = {
        each.parent for each in found if each.parent.resolve().is_relative_to(inside)
    }
    return places, numbers_in(each.name for each in found)
