"""A ticket's open dependencies are offered ahead of it (pitboss#280, pitboss#388).

A ticket that says ``Depends on <owner/repo#n>`` (or is blocked in either other
form, ``ticketblock``) is not offered while that ticket or PR is open, and so is a
PR that fixes such a ticket: it has no step (review, fix, ruling, merge) until the
blocker has merged. The dependency is not left to chance: it takes the place of
the oldest ticket that waits for it in the order, even when it has a lower
priority label or none, with that ticket's label and creation time, whether or not
that ticket has a PR, so a worker is started on it first and never on the one
that waits. A PR stands for the ticket it fixes (keyword: ticket-blocked,
blocked-pull).
"""

from typing import (
    AbstractSet,
    Callable,
    Mapping,
    Protocol,
    Sequence,
    TypeVar,
)


class Waiting(Protocol):
    """What the order reads of an item."""

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
            The blockers' references, none when it waits for nothing.
        """

    @property
    def created_at(self) -> str:
        """When it was opened, or the ticket it stands for was.

        Returns:
            An ISO 8601 time.
        """

    @property
    def ticket(self) -> str:
        """The ticket a PR fixes, or "".

        Returns:
            The ticket's reference.
        """


Each = TypeVar("Each", bound=Waiting)


def index(items: Sequence[Each]) -> Mapping[str, Each]:
    """The items by reference; a PR is also found by the ticket it fixes.

    Args:
        items: the ordered items.

    Returns:
        Each item by its reference, and a PR by its ticket too unless an item
        of that reference is listed.
    """
    found = {each.reference: each for each in items}
    for each in items:
        if each.ticket and each.ticket not in found:
            found[each.ticket] = each
    return found


def roots(item: Waiting, by_reference: Mapping[str, Each]) -> Sequence[str]:
    """The dependencies of a blocked item that are not blocked themselves.

    Args:
        item: an item with blockers.
        by_reference: the items listed (``index``).

    Returns:
        The references, in the order the texts name them, each once. A blocker
        that is listed and blocked is followed to its own blockers; a cycle
        leads nowhere, so it blocks every item in it and offers none.
    """
    seen = {item.reference}
    found: list[str] = []
    pending = list(item.blockers)
    while pending:
        current = pending.pop(0)
        listed = by_reference.get(current)
        name = listed.reference if listed is not None else current
        if name in seen:
            continue
        seen.add(name)
        if listed is not None and listed.blockers:
            pending[0:0] = listed.blockers
        else:
            found.append(name)
    return found


def _missing(
    items: Sequence[Each], skipped: AbstractSet[str]
) -> tuple[Each, str] | None:
    listed = index(items)
    for each in items:
        for name in roots(each, listed) if each.blockers else ():
            if name not in listed and name not in skipped:
                return each, name
    return None


def _join(
    items: Sequence[Each],
    read: Callable[[str, Each], Each | None],
    unavailable: AbstractSet[str],
) -> tuple[list[Each], AbstractSet[str]]:
    listed = list(items)
    skipped = set(unavailable)
    joined: set[str] = set()
    while (found := _missing(listed, skipped)) is not None:
        waiting, reference = found
        skipped.add(reference)
        got = read(reference, waiting)
        if got is not None:
            listed.insert(listed.index(waiting), got)
            joined.add(reference)
    return listed, joined


def _dependents(
    listed: Sequence[Each], by_reference: Mapping[str, Each]
) -> Mapping[str, Sequence[Each]]:
    waiting: dict[str, list[Each]] = {}
    for each in listed:
        for name in roots(each, by_reference) if each.blockers else ():
            waiting.setdefault(name, []).append(each)
    return waiting


def _ahead(
    listed: Sequence[Each], found: Each, dependents: Sequence[Each], joined: bool
) -> Each | None:
    # the oldest item that waits, when the dependency moves ahead of it
    oldest = min(dependents, key=lambda each: each.created_at)
    moved = joined or listed.index(found) > listed.index(oldest)
    return oldest if moved else None


def _move(
    listed: list[Each],
    found: Each,
    oldest: Each | None,
    place: Callable[[Each, Each], Each],
) -> None:
    at = listed.index(found)
    listed.remove(found)
    if oldest is None:
        listed.insert(at, found)
    else:
        listed.insert(listed.index(oldest), place(found, oldest))


Stands = Mapping[str, tuple[Each, Sequence[Each]]]


def _stands(
    waiting: Mapping[str, Sequence[Each]], by_reference: Mapping[str, Each]
) -> Stands[Each]:
    # the dependencies that are listed, with the items that wait for each
    return {
        name: (by_reference[name], each)
        for name, each in waiting.items()
        if name in by_reference
    }


def _blocks(stands: Stands[Each]) -> Mapping[str, Sequence[str]]:
    return {
        name: [each.reference for each in dependents]
        for name, (_, dependents) in stands.items()
    }


def _move_all(
    listed: list[Each],
    stands: Stands[Each],
    joined: AbstractSet[str],
    place: Callable[[Each, Each], Each],
) -> None:
    for name, (found, dependents) in stands.items():
        ahead = _ahead(listed, found, dependents, name in joined)
        _move(listed, found, ahead, place)


def _joined(
    items: Sequence[Each],
    read: Callable[[str, Each], Each | None] | None,
    unavailable: AbstractSet[str],
) -> tuple[list[Each], AbstractSet[str]]:
    if read is None:
        return list(items), frozenset()
    return _join(items, read, unavailable)


def settle(
    items: Sequence[Each],
    read: Callable[[str, Each], Each | None] | None,
    unavailable: AbstractSet[str],
    place: Callable[[Each, Each], Each],
) -> tuple[Sequence[Each], Mapping[str, Sequence[str]]]:
    """Put each open dependency in the place of the oldest item that waits for it.

    A dependency that has no priority label, or whose repository is not
    configured, is added first; its own dependencies are followed.

    Args:
        items: the ordered items, with their blockers named.
        read: reads an open ticket as an item, its blockers named (None for a
            PR, a closed ticket or one the API cannot give); None when no
            ticket may be added (an unreadable PR may work on any ticket).
        unavailable: the references no worker may be started on (a slot holds
            them, or an open PR names them).
        place: the dependency and the oldest item that waits for it, when it
            moved to the oldest one's place; returns the dependency as it
            stands there, with the label and the age of the oldest.

    Returns:
        The items, with each open dependency ahead of the oldest that waits, and
        the references that wait for each dependency that is listed.
    """
    listed, joined = _joined(items, read, unavailable)
    by_reference = index(listed)
    stands = _stands(_dependents(listed, by_reference), by_reference)
    _move_all(listed, stands, joined, place)
    return listed, _blocks(stands)
