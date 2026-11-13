"""The runners a command reaches GitHub through (keyword: one-path, P6).

A command module names the client and builds it; only the reading modules
(``ghapi`` and those that call it) send a request through it.
"""

import dataclasses

from .running import Run


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class GitHub:
    """GitHub's REST API, through ``gh api``.

    Attributes:
        run: the runner reads go through.
        mutate: the runner changes go through (a dry run unless asked).
    """

    run: Run
    mutate: Run


def read_only(run: Run) -> GitHub:
    """The API for a command that only reads (it never changes GitHub).

    Args:
        run: the runner reads go through.

    Returns:
        The API, whose changes go through the same runner.
    """
    return GitHub(run=run, mutate=run)
