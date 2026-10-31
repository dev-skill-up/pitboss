"""The tempdirs and caches a sweep removes by itself, and how they are removed.

Test tempdirs go by age and owner, the package caches that regenerate go only
under disk pressure (keyword: auto-clean, pitboss#120; the rule is in
``rules.md``, "Checkouts and disk").
"""

import fnmatch
import pathlib
from typing import Sequence

from . import cleanconfig, dead
from .machine import Machine

CACHES_IN_HOME = (
    ".cache/pip",
    ".cache/uv",
    ".cache/pre-commit",
    ".npm/_cacache",
    ".cargo/registry/cache",
)


def holds_working(machine: Machine, path: pathlib.Path) -> bool:
    """Whether a path is, or lies above, a directory the command runs in.

    Args:
        machine: the machine.
        path: the path.

    Returns:
        True when removing it would remove the command's own directory.
    """
    return any(each == path or each.is_relative_to(path) for each in machine.working)


def is_mine(machine: Machine, clean: cleanconfig.Clean, path: pathlib.Path) -> bool:
    """Whether a path is a tempdir of the user running: by name, not a link.

    Args:
        machine: the machine.
        clean: the settings.
        path: the path.

    Returns:
        True when its name matches a pattern, it is no link and the user owns it.
    """
    named = any(fnmatch.fnmatchcase(path.name, one) for one in clean.tmp_patterns)
    return (
        named and not machine.fs.is_link(path) and machine.fs.owner(path) == machine.uid
    )


def idle_tempdir(
    machine: Machine, cutoff: float, reason: str, path: pathlib.Path
) -> dead.Candidate | None:
    """A tempdir nobody has touched since a time, if it may go.

    Args:
        machine: the machine.
        cutoff: anything changed after this time is in use.
        reason: why it is dead.
        path: the tempdir.

    Returns:
        The candidate; None when it holds the command's directory, a live
        marker or a mount point, or was changed after the cutoff.
    """
    seen = machine.fs.inspect(path)
    kept = seen.marked or seen.mounts or seen.newest > cutoff
    if kept or holds_working(machine, path):
        return None
    return dead.Candidate(path=path, size=seen.size, reason=reason)


def stale_tempdirs(
    machine: Machine, clean: cleanconfig.Clean, hours: float
) -> Sequence[dead.Candidate]:
    """The tempdirs of the session user that nobody has touched for a while.

    Args:
        machine: the machine.
        clean: the settings.
        hours: how long a tempdir must be untouched.

    Returns:
        The candidates, largest first.
    """
    cutoff = machine.now.timestamp() - hours * 3600
    reason = f"test tempdir untouched for {hours:g} hours"
    entries = (each for root in clean.tmp_roots for each in machine.fs.children(root))
    mine = [each for each in entries if is_mine(machine, clean, each)]
    made = (idle_tempdir(machine, cutoff, reason, each) for each in mine)
    return dead.ordered(dead.present(made))


def cache_candidate(machine: Machine, path: pathlib.Path) -> dead.Candidate | None:
    """A package cache, if it may go.

    Args:
        machine: the machine.
        path: the cache.

    Returns:
        The candidate; None when it is absent, a link, another user's, marked
        live, holds a mount point or holds the command's directory.
    """
    if not machine.fs.exists(path) or machine.fs.is_link(path):
        return None
    seen = machine.fs.inspect(path)
    kept = machine.fs.owner(path) != machine.uid or seen.marked or seen.mounts
    if kept or holds_working(machine, path):
        return None
    return dead.Candidate(
        path=path, size=seen.size, reason="package cache, regenerates"
    )


def regenerable_caches(
    machine: Machine, clean: cleanconfig.Clean
) -> Sequence[dead.Candidate]:
    """The package caches that regenerate: pip's, uv's, npm's and the configured.

    Args:
        machine: the machine.
        clean: the settings.

    Returns:
        The candidates, largest first.
    """
    places = [*(machine.home / name for name in CACHES_IN_HOME), *clean.caches]
    return dead.ordered(dead.present(cache_candidate(machine, each) for each in places))
