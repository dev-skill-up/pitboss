"""Doing the same read for many things at once (keyword: concurrently).

A sweep's time is the time it waits for ``gh`` and ``git``, which is the same
for one call as for sixteen; so each loop over repositories, pull requests or
checkouts asks them all together and keeps their order.
"""

import concurrent.futures
from typing import Callable, Iterable, Iterator, Sequence, TypeVar

WORKERS = 16
_Item = TypeVar("_Item")
_Result = TypeVar("_Result")
_Other = TypeVar("_Other")


def each(
    function: Callable[[_Item], _Result], items: Iterable[_Item]
) -> Sequence[_Result]:
    """Call a function on every item at once.

    Args:
        function: what to call; it may block on a command.
        items: what to call it on.

    Returns:
        The results, in the order of the items. The first failure is raised
        once every call has finished.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(function, items))


def as_ready(
    function: Callable[[_Item], _Result], items: Iterable[_Item]
) -> Iterator[_Result]:
    """Call a function on every item at once, and hand over each in order.

    The first result is handed over as soon as the first call finishes, while
    the others still run.

    Args:
        function: what to call; it may block on a command.
        items: what to call it on.

    Yields:
        The results, in the order of the items.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        yield from pool.map(function, items)


def pair(
    first: Callable[[], _Result], second: Callable[[], _Other]
) -> tuple[_Result, _Other]:
    """Run two reads that do not depend on each other at once.

    Args:
        first: the first read; it may block on a command.
        second: the second read.

    Returns:
        The two results. The first failure is raised once both have finished.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(first)
        other = pool.submit(second)
        return one.result(), other.result()
