"""What the aggressive clean says it freed, and why it left the rest (pitboss#194).

Under disk pressure (keyword: auto-clean) the clean names each directory of the
workspace it kept with the reason, says the bytes each kind of cleaning freed
and, when they fall short of what the file systems need to get under the
pressure, names each kept directory over 500 MB.
"""

import dataclasses
import operator
import pathlib
from typing import AbstractSet, Callable, Sequence

from . import dead, disk, local, machine

KINDS = ("worktrees", "checkouts", "test tempdirs", "package caches")
VERBS = {False: "freed", True: "would be freed"}
BIG_BYTES = 500 * 1000**2
BIG_FORM = "clean: kept {size} {path} ({why}): over 500 MB"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Account:
    """What a clean did, to be told.

    Attributes:
        dry: whether nothing was removed.
        hot: the crowded file systems.
        percent: the disk use from which the clean is aggressive.
        minimum: the free space, in GiB, under which it is aggressive too.
        freed: the bytes each kind of cleaning freed, in the order of ``KINDS``.
        kept: the directories the cleaning left, each with why.
        tied: the worktrees with an open PR, which are never removed.
        measure: the bytes a directory holds.
    """

    dry: bool
    hot: Sequence[machine.Crowded]
    percent: float
    freed: Sequence[int]
    minimum: float = 0.0
    kept: Sequence[dead.Kept]
    tied: Sequence[local.Worktree]
    measure: Callable[[pathlib.Path], int]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Report:
    """What a sweep's clean said and did.

    Attributes:
        lines: what to print.
        told: what the clean did, to be told.
        short: the file systems that had less than the minimum free space
            before the clean (the ``DISK PRESSURE`` rule), as they were.
        left: those of them that still have less after it, as they are.
    """

    lines: Sequence[str]
    told: Account
    short: Sequence[machine.Crowded]
    left: Sequence[machine.Crowded]


def totals(
    gone: Sequence[dead.Candidate],
    dry: bool,
    before: disk.Usage | None,
    after: disk.Usage | None,
) -> str:
    """The last line: how much was removed, and the free space around it.

    Args:
        gone: the paths removed (or, in a dry run, that would be).
        dry: whether nothing was removed: the space ``would be freed``.
        before: the use before.
        after: the use after.

    Returns:
        The line.
    """
    size = disk.size_text(sum(map(operator.attrgetter("size"), gone)))
    return (
        f"clean: {len(gone)} paths removed, {size} {VERBS[dry]}; disk free"
        f" {free_text(before)} before, {free_text(after)} after"
    )


def free_text(usage: disk.Usage | None) -> str:
    """Spell the free space of a use.

    Args:
        usage: the use, or None when it could not be read.

    Returns:
        The size, or ``unknown``.
    """
    return disk.size_text(usage.free) if usage else "unknown"


def open_lines(tied: Sequence[local.Worktree]) -> Sequence[str]:
    """Name the worktrees with an open PR that pressure left alone.

    Args:
        tied: the worktrees with an open PR (``open_worktrees``).

    Returns:
        A line for each.
    """
    return [f"clean: kept {each.path} [{each.branch}] (open PR)" for each in tied]


def directories_left(
    kept: Sequence[dead.Kept],
    candidates: Sequence[dead.Candidate],
    listed: AbstractSet[pathlib.Path],
) -> Sequence[dead.Kept]:
    """The directories of the workspace that the scan left, under pressure.

    The worktrees of the main clone are the worktrees' part's (they say
    themselves why they are kept).

    Args:
        kept: the directories that were not dead, or were live or in use.
        candidates: the dead paths; those not safe to remove are left too.
        listed: the worktrees registered in the main clone.

    Returns:
        A ``Kept`` for each directory that is not a registered worktree and
        was not dead, was live or in use, or was not safe to remove, in the
        order of their paths.
    """
    unsafe = [
        dead.Kept(path=each.path, why=each.kept, size=each.size)
        for each in dead.unsafe(candidates)
    ]
    kept = [each for each in [*kept, *unsafe] if each.path not in listed]
    return sorted(kept, key=lambda each: str(each.path))


def lines(told: Account) -> Sequence[str]:
    """Say what each kind of cleaning freed, and what is left.

    Args:
        told: what the clean did.

    Returns:
        Nothing unless the disk is under pressure. Then a line with the bytes
        freed by each kind, and, when they fall short of what the file systems
        need to get under the pressure, a line for that and one for each
        directory over 500 MB that was kept, with why.
    """
    if not told.hot:
        return []
    head = by_kind(told)
    if sum(told.freed) >= needed(told):
        return [head]
    return [head, short_line(told), *big_lines(told)]


def needed(told: Account) -> int:
    """The bytes the crowded file systems need freed to get under the pressure.

    Args:
        told: what the clean did.

    Returns:
        The bytes.
    """
    return sum(one.over for one in told.hot)


def kinds_text(told: Account) -> str:
    """The bytes each kind of cleaning freed.

    Args:
        told: what the clean did.

    Returns:
        ``worktrees 3.0 GiB, checkouts ...``, one entry for each kind.
    """
    return ", ".join(
        f"{kind} {disk.size_text(size)}" for kind, size in zip(KINDS, told.freed)
    )


def by_kind(told: Account) -> str:
    """The line with the bytes each kind of cleaning freed.

    Args:
        told: what the clean did.

    Returns:
        The line.
    """
    return f"clean: {VERBS[told.dry]} by kind: {kinds_text(told)}"


def short_line(told: Account) -> str:
    """The line that says how far short of the need the cleaning fell.

    Args:
        told: what the clean did.

    Returns:
        The line.
    """
    freed, need = sum(told.freed), needed(told)
    return (
        f"clean: {disk.size_text(freed)} {VERBS[told.dry]},"
        f" {disk.size_text(need - freed)} short of the {disk.size_text(need)}"
        f" needed {goal_text(told)}:"
        " each directory over 500 MB that was kept"
    )


def goal_text(told: Account) -> str:
    """The rule or rules that set the need, as the line spells them.

    Args:
        told: what the clean did.

    Returns:
        ``to get under 90%`` when the percent used set the need of a file
        system, ``to have 5 GiB free`` when the free space did; both, joined by
        ``and``, when each did for one.
    """
    rules = {
        True: f"to have {told.minimum:g} GiB free",
        False: f"to get under {told.percent:g}%",
    }
    named = {one.free_rule for one in told.hot}
    return " and ".join(rules[each] for each in (False, True) if each in named)


def big_kept(told: Account) -> Sequence[tuple[pathlib.Path, int, str]]:
    """The directories over 500 MB that the cleaning kept, each with why.

    Args:
        told: what the clean did.

    Returns:
        The path, the bytes and the reason of each, the largest first.
    """
    open_pr = [dead.Kept(path=each.path, why="open PR") for each in told.tied]
    once = {each.path: each for each in [*told.kept, *open_pr]}
    sizes = {
        path: told.measure(path) if each.size is None else each.size
        for path, each in once.items()
    }
    big = sorted(
        (path for path, size in sizes.items() if size > BIG_BYTES),
        key=lambda path: (-sizes[path], str(path)),
    )
    return [(path, sizes[path], once[path].why) for path in big]


def big_lines(told: Account, form: str = BIG_FORM) -> Sequence[str]:
    """The directories over 500 MB that the cleaning kept, each with why.

    Args:
        told: what the clean did.
        form: the line, with ``{size}``, ``{path}`` and ``{why}`` in it.

    Returns:
        A line for each, the largest first.
    """
    return [
        form.format(size=disk.size_text(size), path=path, why=why)
        for path, size, why in big_kept(told)
    ]
