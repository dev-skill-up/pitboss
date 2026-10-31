"""The cleaning a sweep does first, by itself, and harder when the disk is full.

This is the auto-clean rule (pitboss#120; the rule is in ``rules.md``,
"Checkouts and disk"). No prompt and no dry-run default: a sweep removes the
test tempdirs older than ``[clean] tmp_hours`` that the session user owns, the
finished worktrees and the dead checkouts, and prints what it removed and the
space freed. At or over ``[clean] pressure_percent`` of a filesystem used (90
by default) it also removes tempdirs of a shorter age, every worktree and every
checkout of a repository without an open PR, and the package caches that
regenerate. It never touches a worktree with an open PR, a running worker's
directory (changed within ``idle_hours``, or marked ``.pitboss-live``), the
main clone or the directory it runs in, and it says so.
"""

import dataclasses
import functools
import operator
import pathlib
from typing import AbstractSet, Sequence

from . import (
    cleaning,
    cleanconfig,
    dead,
    deadscan,
    disk,
    local,
    machine as machines,
    tempclean,
    worktrees,
)
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
    """

    lines: Sequence[str]
    gone: Sequence[dead.Candidate]


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
    where = ", ".join(f"{each.place} {each.percent:.0f}%" for each in hot)
    age = f"{clean.pressure_tmp_hours:g} hours"
    return (
        f"clean: DISK OVER {limit} ({where}): aggressive: test tempdirs untouched"
        f" for {age}, every worktree and checkout without an open PR, package caches"
    )


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
        f" directory (changed within {hours:g} hours or marked .pitboss-live),"
        " the main clone, the directory this command runs in"
    )


def kept_lines(job: Job) -> Sequence[str]:
    """Name the worktrees with an open PR that pressure left alone.

    Args:
        job: the cleaning.

    Returns:
        A line for each; none unless the disk is under pressure.
    """
    if not job.hot:
        return []
    return [
        f"clean: kept {each.path} [{each.branch}] (open PR)"
        for each in worktrees.tied_to_open_pr(job.look)
    ]


def removal_for(job: Job) -> tempclean.Removing:
    """How this cleaning removes plain paths.

    Args:
        job: the cleaning.

    Returns:
        Nothing in a dry run, else through the machine's file system.
    """
    if job.option.dry:
        return tempclean.removing_nothing()
    return tempclean.removing_for_real(job.machine)


def worktrees_part(job: Job) -> Part:
    """Remove the finished worktrees, or only list them.

    Args:
        job: the cleaning.

    Returns:
        The worktrees' own lines; they report their space themselves.
    """
    look, option = job.look, job.option
    decide = local.pressure_reason if job.hot else local.finished_reason
    if option.list_only and not job.hot:
        return Part(lines=worktrees.stale_lines(look, job.machine.now, decide), gone=[])
    action = worktrees.Action(run=option.run, dry=option.dry)
    lines = worktrees.remove_lines(look, action, job.machine.now, decide)
    return Part(lines=lines, gone=[])


def scan_checkouts(
    job: Job,
) -> tuple[deadscan.Findings, Sequence[dead.Candidate]]:
    """Find the dead checkouts, scratch and root files that are safe.

    Args:
        job: the cleaning.

    Returns:
        What the scan found, and the paths chosen for removal. The linked
        worktrees were judged by ``worktrees_part`` (git keeps one with
        untracked files); only pressure takes them as dead paths too.
    """
    look = job.look
    decide = deadscan.pressure_reason if job.hot else deadscan.checkout_reason
    found = deadscan.scan(look, job.machine.now.timestamp(), decide)
    chosen, _ = cleaning.choose(found.candidates, None, roots(look))
    return found, [each for each in chosen if job.hot or each.prune is None]


def checkout_lines(
    found: deadscan.Findings,
    results: Sequence[tuple[dead.Candidate, str]],
    note: str,
) -> Sequence[str]:
    """Say what happened to each checkout.

    Args:
        found: what the scan found.
        results: each path with the reason it stayed, empty when it went.
        note: what follows the line of a path removed.

    Returns:
        The lines: the fetches that failed, then a line for each path.
    """
    return [
        *(
            f"fetch failed in {name}: its checkouts are not judged"
            for name in found.unfetched
        ),
        *(
            cleaning.stuck_line(each, why) if why else cleaning.removed_line(each, note)
            for each, why in results
        ),
    ]


def checkouts_part(job: Job) -> Part:
    """Remove the dead checkouts, scratch and root files that are safe.

    Args:
        job: the cleaning.

    Returns:
        The lines, and the paths that are gone; nothing when the worktrees are
        only listed and the disk is not under pressure.
    """
    if job.option.list_only and not job.hot:
        return nothing()
    look, option = job.look, job.option
    found, chosen = scan_checkouts(job)
    cutoff = job.machine.now.timestamp() - look.settings.idle_hours * 3600
    how = cleaning.Removal(
        run=option.run,
        recheck=functools.partial(dead.recheck, look, cutoff),
        batch=tempclean.BATCH,
        dry=option.dry,
    )
    results = list(cleaning.removals(how, chosen))
    gone = [each for each, why in results if not why]
    cleaning.prune(option.run, gone)
    return Part(lines=checkout_lines(found, results, removal_for(job).note), gone=gone)


def tempdirs_part(job: Job) -> Part:
    """Remove the session user's test tempdirs that nobody has touched.

    Args:
        job: the cleaning.

    Returns:
        The lines and the paths gone; the age is shorter under pressure.
    """
    clean = job.look.clean
    hours = clean.pressure_tmp_hours if job.hot else clean.tmp_hours
    found = tempclean.stale_tempdirs(job.machine, clean, hours)
    lines, gone = tempclean.remove_found(removal_for(job), found)
    return Part(lines=lines, gone=gone)


def caches_part(job: Job) -> Part:
    """Remove the package caches that regenerate, under pressure only.

    Args:
        job: the cleaning.

    Returns:
        The lines and the paths gone; nothing when the disk is not crowded.
    """
    if not job.hot:
        return nothing()
    found = tempclean.regenerable_caches(job.machine, job.look.clean)
    lines, gone = tempclean.remove_found(removal_for(job), found)
    return Part(lines=lines, gone=gone)


def clean_lines(look: dead.Look, machine: Machine, option: Option) -> Sequence[str]:
    """Clean, and say what was removed and the space freed.

    Args:
        look: what to look at and keep.
        machine: the machine.
        option: how to clean.

    Returns:
        The lines: the mode, the worktrees, what was removed, what is never
        touched, and the totals.
    """
    clean = look.clean
    hot = machines.find_crowded(machine, paths_watched(look), clean.pressure_percent)
    job = Job(look=look, machine=machine, option=option, hot=hot)
    before = machine.usage(look.settings.project.workspace)
    parts = [worktrees_part(job), checkouts_part(job), tempdirs_part(job)]
    parts.append(caches_part(job))
    after = machine.usage(look.settings.project.workspace)
    gone = [each for part in parts for each in part.gone]
    verb = "would be freed" if option.dry else "freed"
    return [
        header(hot, clean),
        *(text for part in parts for text in part.lines),
        *kept_lines(job),
        never_line(look),
        totals(gone, verb, before, after),
    ]


def totals(
    gone: Sequence[dead.Candidate],
    verb: str,
    before: disk.Usage | None,
    after: disk.Usage | None,
) -> str:
    """The last line: how much was removed, and the free space around it.

    Args:
        gone: the paths removed (or, in a dry run, that would be).
        verb: what happens to the space: ``freed`` or ``would be freed``.
        before: the use before.
        after: the use after.

    Returns:
        The line.
    """
    size = disk.size_text(sum(map(operator.attrgetter("size"), gone)))
    return (
        f"clean: {len(gone)} paths removed, {size} {verb}; disk free"
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
