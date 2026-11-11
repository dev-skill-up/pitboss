"""The ``BLOCKED`` line of a ticket that cannot be worked on (pitboss#163)."""

from typing import Protocol, Sequence

from . import workitem
from .markers import Marker


class Blocked(Protocol):
    """A ticket or PR that waits for open blockers."""

    @property
    def reference(self) -> str:
        """The item's ``owner/name#number``.

        Returns:
            The reference.
        """

    @property
    def blockers(self) -> Sequence[str]:
        """The open tickets and PRs it waits for.

        Returns:
            The blockers' references.
        """


def line(reference: str, blocker: str, *others: str) -> str:
    """The line that says a ticket is not offered because of an open blocker.

    Args:
        reference: the ticket's, or a PR's, ``owner/name#number``.
        blocker: the open ticket or PR, ``owner/name#number``.
        *others: the other open blockers (pitboss#388).

    Returns:
        The ``BLOCKED`` line, the blockers joined by commas.
    """
    names = ", ".join((blocker, *others))
    return f"{Marker.BLOCKED.text} {reference} by {names}"


def of(item: Blocked) -> str:
    """The line of an item that waits for open blockers.

    Args:
        item: a ticket or PR with its ``blockers`` named.

    Returns:
        The ``BLOCKED`` line; for a PR whose red ``canonical-files`` asks for a
        line of the allowlist, the line follows (keyword: allowlist-miss).
    """
    said = line(item.reference, *item.blockers)
    if isinstance(item, workitem.Allowing):
        return f"{said}; allowlist line: {item.allowlist}"
    return said
