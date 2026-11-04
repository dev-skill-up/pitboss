"""The ``BLOCKED`` line of a ticket that cannot be worked on (pitboss#163)."""

from .markers import Marker


def line(reference: str, blocker: str) -> str:
    """The line that says a ticket is not offered because of an open blocker.

    Args:
        reference: the ticket's ``owner/name#number``.
        blocker: the open ticket or PR, ``owner/name#number``.

    Returns:
        The ``BLOCKED`` line.
    """
    return f"{Marker.BLOCKED.text} {reference} by {blocker}"
