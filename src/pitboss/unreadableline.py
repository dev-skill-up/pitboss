"""The line of a PR one of whose API calls failed (keyword: unreadable-pull)."""

from . import shapes
from .markers import Marker


def unreadable_line(pull: shapes.Unreadable) -> str:
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
