"""The words of an item form (``next``, ``slots next``): none, or one ticket or PR."""

import re
import sys
from typing import NoReturn, Sequence

from . import config, ledger

_FULL_REFERENCE = re.compile(r"^[\w.-]+/[\w.-]+#\d+$")
TAKES_ONE = "next takes one ticket or PR, or none"
TAKES_FULL = "next takes a ticket as owner/repo#N, repo#N or #N"


def _refuse(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def reference(words: Sequence[str], repo: config.Repo) -> str | None:
    """The item the words name.

    Args:
        words: the words after ``next`` or ``slots next``.
        repo: the project's repository, the owner of a bare ``#N``.

    Returns:
        The item as ``owner/repo#N``; None for no words. Words it does not take
        exit 2 on standard error.
    """
    if len(words) > 1:
        _refuse(TAKES_ONE)
    if not words:
        return None
    named = ledger.reference(words[0], repo)
    if not _FULL_REFERENCE.match(named):
        _refuse(TAKES_FULL)
    return named
