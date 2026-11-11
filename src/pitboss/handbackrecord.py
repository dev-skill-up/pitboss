"""The record of the heads a hand-back was accepted for (keyword: hand-back-done).

``hand-back-check`` writes it in the worktree's git directory; ``slots`` reads it
to count the worker done (pitboss#471).
"""

import pathlib

RECORD = "pitboss-hand-back"


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


def record(git_directory: pathlib.Path, head: str) -> None:
    """Record that a hand-back was accepted for a head.

    Args:
        git_directory: the worktree's git directory.
        head: the head.
    """
    try:
        with (git_directory / RECORD).open("a", encoding="utf-8") as kept:
            kept.write(f"{head}\n")
    except OSError:  # pragma: no cover
        return
