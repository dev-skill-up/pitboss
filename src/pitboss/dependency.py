"""A ticket's open dependency is offered ahead of it (pitboss#280).

A ticket that says ``Depends on <owner/repo#n>`` (or is blocked in either other
form, ``ticketblock``) is not offered while that ticket or PR is open. The
dependency is not left to chance: it takes the blocked ticket's place in the
order, even when it has a lower priority label or none, so a worker is started on
it first and never on the ticket that waits (keyword: ticket-blocked).
"""

from typing import AbstractSet, Callable, Mapping, Protocol, Sequence, TypeVar


class Waiting(Protocol):
    """What the order reads of an item."""

    @property
    def reference(self) -> str:
        """The item's ``owner/name#number``.

        Returns:
            The reference.
        """

    @property
    def blocker(self) -> str:
        """The open ticket or PR it waits for, or "".

        Returns:
            The blocker's reference.
        """

    @property
    def priority(self) -> int:
        """The index of its priority label.

        Returns:
            The index.
        """


Each = TypeVar("Each", bound=Waiting)


def root(item: Waiting, by_reference: Mapping[str, Waiting]) -> str:
    """The first dependency of a blocked ticket that is not blocked itself.

    Args:
        item: a ticket with a blocker.
        by_reference: the items listed, by reference.

    Returns:
        The reference, or "" when the dependencies lead back to the ticket
        (a cycle blocks every ticket in it).
    """
    seen = {item.reference}
    current = item.blocker
    while current in by_reference and by_reference[current].blocker:
        if current in seen:
            return ""
        seen.add(current)
        current = by_reference[current].blocker
    return "" if current in seen else current


def _missing(
    items: Sequence[Each], skipped: AbstractSet[str]
) -> tuple[Each, str] | None:
    listed = {each.reference: each for each in items}
    wanted = ((each, root(each, listed)) for each in items if each.blocker)
    unlisted = (pair for pair in wanted if pair[1] and pair[1] not in listed)
    return next((pair for pair in unlisted if pair[1] not in skipped), None)


def join(
    items: Sequence[Each],
    read: Callable[[str, Each], Each | None],
    unavailable: AbstractSet[str],
) -> Sequence[Each]:
    """Add the open tickets that listed tickets wait for and the list lacks.

    Such a ticket has no priority label, or its repository is not configured.
    It stands where the ticket that waits for it stands, and its own dependency
    is followed.

    Args:
        items: the ordered items, with their blockers named.
        read: reads an open ticket as an item with the priority and the age of
            the ticket that waits for it, its blocker named (None for a PR, a closed
            ticket or one the API cannot give).
        unavailable: the references no worker may be started on (a slot holds
            them, or an open PR names them).

    Returns:
        The items, with the tickets added.
    """
    listed = list(items)
    skipped = set(unavailable)
    while (found := _missing(listed, skipped)) is not None:
        waiting, reference = found
        skipped.add(reference)
        joined = read(reference, waiting)
        if joined is not None:
            listed.insert(listed.index(waiting), joined)
    return listed


def order(
    items: Sequence[Each], inherit: Callable[[Each, Each], Each]
) -> Sequence[Each]:
    """Put each dependency that is listed after its ticket in the ticket's place.

    Args:
        items: the ordered items, with their blockers named.
        inherit: the dependency as it stands in the ticket's place, with the
            priority and the age of the ticket that waits for it.

    Returns:
        The items, with each open dependency ahead of its ticket.
    """
    listed = list(items)
    for waiting in [each for each in items if each.blocker]:
        by_reference = {each.reference: each for each in listed}
        found = by_reference.get(root(waiting, by_reference))
        if found is not None and listed.index(found) > listed.index(waiting):
            listed.remove(found)
            listed.insert(listed.index(waiting), inherit(found, waiting))
    return listed
