"""What a sweep's clean is given and what each kind of cleaning answers."""

import dataclasses
import pathlib
from typing import AbstractSet, Sequence

from . import dead
from . import machine as machines
from .machine import Crowded, Machine
from .running import Run


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Option:
    """How a run cleans.

    Attributes:
        run: the runner for changes (``rm`` and ``git worktree remove``).
        dry: whether to remove nothing.
        list_only: whether the finished worktrees are only listed, and the
            dead checkouts left, unless the disk is under pressure.
    """

    run: Run
    dry: bool
    list_only: bool = False


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Job:
    """One job: what it looks at, on what machine, and how hard.

    Attributes:
        look: what to look at and keep.
        machine: the machine.
        option: how to clean.
        hot: the crowded file systems; any makes the cleaning aggressive.
    """

    look: dead.Look
    machine: Machine
    option: Option
    hot: Sequence[Crowded]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Part:
    """What one kind of cleaning did.

    Attributes:
        lines: what to print.
        gone: the paths removed, or that would be in a dry run.
        freed: the bytes freed, or that would be in a dry run.
        kept: the directories this kind of cleaning left, each with why.
    """

    lines: Sequence[str]
    gone: Sequence[dead.Candidate]
    freed: int = 0
    kept: Sequence[dead.Kept] = ()


def nothing() -> Part:
    """A part that did nothing.

    Returns:
        The part.
    """
    return Part(lines=[], gone=[])


def paths_watched(look: dead.Look) -> Sequence[pathlib.Path]:
    """The paths whose file systems are watched for pressure.

    Args:
        look: what to look at and keep.

    Returns:
        The workspace, the tempdir roots and the scratch directories.
    """
    return [look.settings.project.workspace, *look.clean.tmp_roots, *look.clean.scratch]


def roots(look: dead.Look) -> AbstractSet[pathlib.Path]:
    """The directories whose entries may be removed.

    Args:
        look: what to look at and keep.

    Returns:
        The workspace, the scratch directories and the root of the files.
    """
    return {look.settings.project.workspace, *look.clean.scratch, look.watch.root}


def crowded_now(look: dead.Look, machine: Machine) -> Sequence[Crowded]:
    """The file systems that are crowded: over the percent or short of free space.

    Args:
        look: what to look at and keep.
        machine: the machine.

    Returns:
        The file systems; any makes the cleaning aggressive (pitboss#205).
    """
    clean = look.clean
    return machines.find_crowded(
        machine, paths_watched(look), clean.pressure_percent, clean.min_free_gib
    )


def short_of(found: Sequence[Crowded]) -> Sequence[Crowded]:
    """The crowded file systems that have less than the minimum free space.

    Args:
        found: the crowded file systems.

    Returns:
        Those of them.
    """
    return [each for each in found if each.short]
