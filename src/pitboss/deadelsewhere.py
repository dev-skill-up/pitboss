"""The dead paths beside the checkouts: scratch entries and the container's root files.

A look at the machine judges them all at once (keyword: clean-container,
pitboss#453); the walks are made one after another and the questions to ``git``
together.
"""

import pathlib
from typing import Sequence

from . import concurrently, container, dead


def considered(
    look: dead.Look, paths: Sequence[tuple[pathlib.Path, str]], cutoff: float
) -> Sequence[dead.Candidate]:
    """Measure many dead paths at once, and check that each is safe.

    The walks are made one after another and the questions to ``git`` together
    (keyword: walk-speed, pitboss#453).

    Args:
        look: what to look at and keep.
        paths: each path and why it is dead.
        cutoff: anything changed after this time is in use.

    Returns:
        The candidates, in the order of the paths; a path that is live or in use
        is left out.
    """
    walks = look.scan.walks
    if walks:
        # walks are one after another: threads walking at once wait for each
        # other's file system calls and take several times as long
        for place, _ in paths:
            if not dead.recent(place, cutoff):
                walks(place)
    made = concurrently.each(
        lambda each: dead.consider(look, each[0], each[1], cutoff), paths
    )
    return dead.present(made)


def dead_root_files(look: dead.Look, cutoff: float) -> Sequence[dead.Candidate]:
    """The files in a container's root written well after it started.

    Args:
        look: what to look at and keep.
        cutoff: anything changed after this time is in use.

    Returns:
        The candidates; none when the marker file is absent.
    """
    watch = look.watch
    if not watch.marker.exists():
        return []
    after = container.cutoff(watch.marker, watch.hours)
    reason = f"written over {watch.hours:g} hours after the container started"
    files = container.newer_files(watch.root, after)
    return considered(look, [(each.path, reason) for each in files], cutoff)


def dead_scratch(look: dead.Look, cutoff: float) -> Sequence[dead.Candidate]:
    """The entries of the scratch directories that nobody uses.

    Args:
        look: what to look at and keep.
        cutoff: anything changed after this time is in use.

    Returns:
        The candidates.
    """
    hours = look.settings.idle_hours
    reason = f"unreferenced scratch, untouched for {hours:g} hours"
    entries = [
        entry
        for root in look.clean.scratch
        if root.is_dir()
        for entry in sorted(root.iterdir())
    ]
    return considered(look, [(entry, reason) for entry in entries], cutoff)


def plain_directories(workspace: pathlib.Path) -> Sequence[dead.Kept]:
    """The directories of the workspace that are not git checkouts.

    They are never judged; a hidden one is not named.

    Args:
        workspace: the directory.

    Returns:
        A ``Kept`` for each, sorted.
    """
    return [
        dead.Kept(path=path, why=dead.NOT_A_CHECKOUT)
        for path in sorted(workspace.iterdir())
        if path.is_dir()
        and not path.is_symlink()
        and not path.name.startswith(".")
        and not (path / ".git").exists()
    ]


def dead_elsewhere(look: dead.Look, cutoff: float) -> Sequence[dead.Candidate]:
    """The dead scratch entries and the dead files in the container's root.

    Args:
        look: what to look at and keep.
        cutoff: anything changed after this time is in use.

    Returns:
        The candidates.
    """
    found = [*dead_scratch(look, cutoff), *dead_root_files(look, cutoff)]
    look.scan.lap("checkouts, scratch and root files judged")
    return found
