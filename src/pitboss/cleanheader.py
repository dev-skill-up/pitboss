"""The first and the "never touched" lines of a sweep's cleaning."""

from typing import Sequence

from . import cleanconfig, dead, disk
from .machine import Crowded


def header(hot: Sequence[Crowded], clean: cleanconfig.Clean) -> str:
    """The line that says which cleaning this is.

    Args:
        hot: the crowded file systems.
        clean: the settings.

    Returns:
        The line.
    """
    limit = f"{clean.pressure_percent:g}%"
    if not hot:
        age = f"{clean.tmp_hours:g} hours"
        return (
            f"clean: disk under {limit} used: test tempdirs untouched for {age},"
            " finished worktrees and checkouts"
        )
    where = ", ".join(spell(each) for each in hot)
    age = f"{clean.pressure_tmp_hours:g} hours"
    over = any(each.percent >= clean.pressure_percent for each in hot)
    rule = f"OVER {limit}" if over else f"UNDER {clean.min_free_gib:g} GiB FREE"
    return (
        f"clean: DISK {rule} ({where}): aggressive: test tempdirs untouched"
        f" for {age}, every worktree and checkout without an open PR, package caches"
    )


def spell(each: Crowded) -> str:
    """Name a crowded file system.

    Args:
        each: the file system.

    Returns:
        Its place and the percent used, and the free space when it is too little.
    """
    text = f"{each.place} {each.percent:.0f}%"
    return f"{text}, {disk.size_text(each.free)} free" if each.short else text


def never_line(look: dead.Look) -> str:
    """Say what the cleaning never touches.

    Args:
        look: what to look at and keep.

    Returns:
        The line.
    """
    hours = look.settings.idle_hours
    return (
        "clean: never touched: a worktree with an open PR, a running worker's"
        f" directory (changed within {hours:g} hours or marked .pitboss-live; a"
        " merged worktree's marker is ignored under disk pressure, except the one"
        " whose PR merged last, and at any disk level once it is older than 6"
        " hours),"
        " the main clone, the directory this command runs in"
    )
