"""A fake git for the tests of a head that ran green (pitboss#345)."""

import pathlib
from typing import Callable, Sequence

from .test_nox import Done, cannot_say


def answering(
    head: str, directory: pathlib.Path, status: str
) -> Callable[[Sequence[str]], Done]:
    """A git that knows a head, a git directory and a status, and nothing else.

    Args:
        head: the head commit.
        directory: the git directory.
        status: what ``git status --porcelain`` prints.

    Returns:
        The function that answers a git command line; the diff cannot be said,
        so every test is run.
    """
    known = {
        ("git", "rev-parse", "HEAD"): head,
        ("git", "rev-parse", "--absolute-git-dir"): directory.as_posix(),
        ("git", "status", "--porcelain"): status,
    }

    def run(cmdargs: Sequence[str]) -> Done:
        key = tuple(cmdargs)
        if key in known:
            return Done(returncode=0, stdout=known[key] + "\n")
        return cannot_say(cmdargs)

    return run
