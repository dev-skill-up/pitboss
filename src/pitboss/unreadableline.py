"""The line of a PR one of whose API calls failed (keyword: unreadable-pull)."""

from typing import Sequence

from . import pulls
from .markers import Marker


def print_withheld(found: Sequence[pulls.Read]) -> None:
    """Say that tickets are not offered because a PR could not be read.

    Args:
        found: the open PRs, read or not.
    """
    count = sum(1 for each in found if isinstance(each, pulls.Unreadable))
    if count:
        print(
            f"{Marker.UNREADABLE.text} tickets: not offered as new work, {count}"
            " open PR(s) could not be read and may already work on them; sweep again"
        )


def unreadable_line(pull: pulls.Unreadable) -> str:
    """The line for a PR one of whose API calls failed.

    Args:
        pull: the PR.

    Returns:
        The line, naming the call and its status.
    """
    return (
        f"{Marker.UNREADABLE.text} {pull.reference}: {pull.call} answered"
        f" {pull.status}"
    )
