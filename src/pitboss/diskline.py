"""The ``DISK PRESSURE`` lines of a sweep: little free space, what the clean did.

Under the minimum free space the sweep's clean is the aggressive pass, as over
the percent used (pitboss#205): the line says so, how many bytes it freed and,
when the free space is still under the minimum, each directory over 500 MB that
was kept, with why.
"""

from typing import Sequence

from . import account, autoclean, disk
from .markers import Marker
from .machine import Crowded


def started(each: Crowded, minimum: float, told: account.Account) -> str:
    """The line for one file system that was short of free space.

    Args:
        each: the file system, as it was before the clean.
        minimum: the minimum free space, in GiB.
        told: what the clean did.

    Returns:
        The line: the free space, the pass started and the bytes it freed.
    """
    freed = disk.size_text(sum(told.freed))
    return (
        f"{Marker.DISK_PRESSURE.text} {each.place}: {disk.size_text(each.free)}"
        f" free, under {minimum:g} GiB: the aggressive clean started (worktrees"
        f" and clones of every repository in the workspace, checkouts, test"
        f" tempdirs, package caches): {account.VERBS[told.dry]} {freed}"
        f" ({account.kinds_text(told)})"
    )


def remaining(each: Crowded, minimum: float, told: account.Account) -> Sequence[str]:
    """The lines for a file system that is still short of free space.

    Args:
        each: the file system, as it is after the clean.
        minimum: the minimum free space, in GiB.
        told: what the clean did.

    Returns:
        A line saying so, then each directory over 500 MB that was kept, with
        why (or that there is none).
    """
    head = (
        f"{Marker.DISK_PRESSURE.text} {each.place}: still {disk.size_text(each.free)}"
        f" free, under {minimum:g} GiB: each directory over 500 MB that was kept"
    )
    big = [
        f"  {disk.size_text(size)} {path} ({why})"
        for path, size, why in account.big_kept(told)
    ]
    return [head, *(big or ["  no kept directory is over 500 MB"])]


def lines(report: autoclean.Report, minimum: float) -> Sequence[str]:
    """Warn when a filesystem the cleaning covers was short of free space.

    Nothing is said while there is room.

    Args:
        report: what the clean said and did.
        minimum: the minimum free space, in GiB.

    Returns:
        For each file system that was short, the pass started and the bytes
        it freed; for each still short, the directories over 500 MB kept.
    """
    still = {each.place: each for each in report.left}
    said = []
    for each in report.short:
        said.append(started(each, minimum, report.told))
        if each.place in still:
            said.extend(remaining(still[each.place], minimum, report.told))
    return said
