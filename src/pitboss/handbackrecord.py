"""The record of the heads a hand-back was accepted for (keyword: hand-back-done).

``hand-back-check`` writes it in the worktree's git directory; ``slots`` reads it
to count the worker done (pitboss#471).
"""

import pathlib
import urllib.parse
from typing import AbstractSet

from . import handbacks

RECORD = "pitboss-hand-back"
KEPT = "pitboss-hand-backs"


def kept(common: pathlib.Path, branch: str) -> pathlib.Path:
    """The directory that keeps a branch's record whatever worktree exists.

    The keyword is durable-record (pitboss#513): a record only in a worktree's git
    directory is gone with the worktree, and a PR then looks as no worker held it.

    Args:
        common: the main clone's git directory.
        branch: the PR's head branch.

    Returns:
        The directory ``states`` and ``record`` take; it need not exist yet.
    """
    return common / KEPT / urllib.parse.quote(branch, safe="")


def recorded(git_directory: pathlib.Path, head: str) -> bool:
    """Whether a hand-back was already accepted for a head.

    Args:
        git_directory: the worktree's git directory.
        head: the head the hand-back is for.

    Returns:
        True when the record names it.
    """
    try:
        text = (git_directory / RECORD).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    return head in text.split()


def states(git_directory: pathlib.Path) -> AbstractSet[tuple[str, str, str]]:
    """The heads, bodies and rulings a worktree's hand-backs were accepted for.

    Args:
        git_directory: the worktree's git directory.

    Returns:
        Each ``(head, body digest, ruling address)``; an older line, which holds
        only the head, covers any body and ruling.
    """
    try:
        text = (git_directory / RECORD).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return frozenset()
    found = set()
    for line in text.splitlines():
        words = line.split()
        padded = [*words, handbacks.ANY, handbacks.ANY][:3] if words else []
        if padded:
            found.add((padded[0], padded[1], padded[2]))
    return frozenset(found)


def record(git_directory: pathlib.Path, head: str, digest: str, ruling: str) -> None:
    """Record that a hand-back was accepted for a head, a body and a ruling.

    Args:
        git_directory: the worktree's git directory.
        head: the head.
        digest: the digest of the PR body.
        ruling: the address of the PR's newest ruling, ``handbacks.NO_RULING``.
    """
    try:
        git_directory.mkdir(parents=True, exist_ok=True)
        with (git_directory / RECORD).open("a", encoding="utf-8") as written:
            written.write(f"{head} {digest} {ruling}\n")
    except OSError:  # pragma: no cover
        return
