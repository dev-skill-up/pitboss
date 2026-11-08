"""The cleaning a sweep does first, by itself, and harder when the disk is full.

This is the auto-clean rule (pitboss#120; the rule is in ``rules.md``,
"Checkouts and disk"). No prompt and no dry-run default: a sweep removes the
test tempdirs older than ``[clean] tmp_hours`` that the session user owns and
no running process works in, the finished worktrees and the dead checkouts, and
prints what it removed and the space freed. At or over ``[clean]
pressure_percent`` of a filesystem used (90 by default), or when it has less
than ``[clean] min_free_gib`` free (5 GiB by default; pitboss#205), it also
removes tempdirs of a shorter age, every worktree and every checkout of a
repository without an open PR, and the package caches that regenerate. It never
touches a worktree with an open PR, a running worker's
directory (changed within ``idle_hours``, or marked ``.pitboss-live``; a merged
worktree's marker is ignored under disk pressure, except the one whose PR merged
last, and, at any disk level, once it is older than a worker's task, 6 hours:
``workhours``), the main clone or the directory it runs in, and it says so.
Under pressure it also judges every directory of the workspace that is not a
registered worktree (a full clone included) by the PRs of its own ``origin``,
names each it keeps with why, says the bytes freed by each kind and, when they
fall short, each kept directory over 500 MB (``account``, pitboss#194).
"""

import dataclasses
import functools
from typing import Callable, Sequence

from . import (
    account,
    cleaning,
    cleanheader,
    dead,
    deadscan,
    judging,
    local,
    logline,
    tempclean,
    worktrees,
)
from .cleanjob import Job, Option, Part, crowded_now, nothing, roots, short_of
from .machine import Machine


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
    weigh = judging.under_pressure if job.hot else judging.at_ease
    action = worktrees.Action(run=option.run, dry=option.dry, weigh=weigh)
    done = worktrees.removal(look, action, job.machine.now, decide)
    return Part(
        lines=done.lines,
        gone=[],
        freed=done.freed,
        kept=done.left,
        heads=done.heads,
    )


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


def keep_going(each: dead.Candidate) -> str:
    """Never hold a path back from its removal.

    Args:
        each: the candidate.

    Returns:
        Empty: it may go.
    """
    return ""


def removal_part(
    job: Job,
    found: Sequence[dead.Candidate],
    recheck: Callable[[dead.Candidate], str],
) -> Part:
    """Remove paths, saying what happened to each.

    Args:
        job: the job.
        found: the paths.
        recheck: why a path must not go now, looked at just before its removal.

    Returns:
        The lines and the paths gone (all of them in a dry run).
    """
    option = job.option
    how = cleaning.Removal(
        run=option.run, recheck=recheck, batch=cleaning.DEFAULT_BATCH, dry=option.dry
    )
    done = cleaning.remove_paths(how, found)
    return Part(lines=done.lines, gone=done.gone, freed=done.freed, kept=done.stuck)


def checkouts_part(job: Job) -> Part:
    """Remove the dead checkouts, scratch and root files that are safe.

    Args:
        job: the job.

    Returns:
        The lines, and the paths that are gone; nothing when the worktrees are
        only listed and the disk is not under pressure. Under pressure, a line
        for each directory of the workspace that was kept, with why.
    """
    if job.option.list_only and not job.hot:
        return nothing()
    found, chosen = scan_checkouts(job)
    cutoff = job.machine.now.timestamp() - job.look.settings.idle_hours * 3600
    recheck = functools.partial(dead.recheck, job.look, cutoff)
    part = removal_part(job, chosen, recheck)
    cleaning.prune(job.option.run, part.gone)
    failed = [
        f"fetch failed in {name}: its checkouts are not judged"
        for name in found.unfetched
    ]
    left = directories_left(job, found)
    said = cleaning.kept_checkouts(left)
    return dataclasses.replace(
        part, lines=[*failed, *part.lines, *said], kept=[*left, *part.kept]
    )


def directories_left(job: Job, found: deadscan.Findings) -> Sequence[dead.Kept]:
    """The directories of the workspace the scan left, under pressure.

    Args:
        job: the job.
        found: what the scan found.

    Returns:
        A ``Kept`` for each, with why; none unless the disk is under pressure.
    """
    if not job.hot:
        return []
    listed = worktrees.registered(job.look)
    return account.directories_left(found.kept, found.candidates, listed)


def tempdirs_part(job: Job) -> Part:
    """Remove the session user's test tempdirs that nobody touched or works in.

    Args:
        job: the job.

    Returns:
        The lines and the paths gone; the age is shorter under pressure.
    """
    clean = job.look.clean
    hours = clean.pressure_tmp_hours if job.hot else clean.tmp_hours
    return removal_part(
        job, tempclean.stale_tempdirs(job.machine, clean, hours), keep_going
    )


def caches_part(job: Job) -> Part:
    """Remove the package caches that regenerate, under pressure only.

    Args:
        job: the job.

    Returns:
        The lines and the paths gone; nothing when the disk is not crowded.
    """
    if not job.hot:
        return nothing()
    found = tempclean.regenerable_caches(job.machine, job.look.clean)
    return removal_part(job, found, keep_going)


def all_parts(job: Job) -> Sequence[Part]:
    """Do each kind of cleaning, in order.

    Args:
        job: the job.

    Returns:
        What each did: the worktrees, the checkouts, the tempdirs, the caches.
    """
    return [
        worktrees_part(job),
        checkouts_part(job),
        tempdirs_part(job),
        caches_part(job),
    ]


def run_parts(job: Job) -> tuple[Sequence[Part], str]:
    """Do each kind of cleaning, and total what it removed.

    Args:
        job: the job.

    Returns:
        What each kind did, and the totals line (the paths removed, the bytes
        and the free space of the workspace before and after).
    """
    use = functools.partial(job.machine.usage, job.look.settings.project.workspace)
    before = use()
    parts = all_parts(job)
    gone = [each for part in parts for each in part.gone]
    return parts, account.totals(gone, job.option.dry, before, use())


def parts_lines(parts: Sequence[Part]) -> Sequence[str]:
    """What the kinds of cleaning print, in order.

    Args:
        parts: what each kind did.

    Returns:
        Their lines.
    """
    return [text for part in parts for text in part.lines]


def clean_report(look: dead.Look, machine: Machine, option: Option) -> account.Report:
    """Clean, and say what was removed and the space freed.

    Args:
        look: what to look at and keep.
        machine: the machine.
        option: how to clean.

    Returns:
        The lines (the mode, the worktrees, what was removed, what is never
        touched, and the totals) and what the ``DISK PRESSURE`` line needs.
    """
    hot = crowded_now(look, machine)
    job = Job(look=look, machine=machine, option=option, hot=hot)
    parts, totals = run_parts(job)
    tied = worktrees.tied_to_open_pr(look) if hot else []
    told = told_of(job, parts, tied)
    log_clean(job, told)
    head = cleanheader.header(hot, look.clean)
    tail = [cleanheader.never_line(look), totals, *account.lines(told)]
    return account.Report(
        lines=[head, *parts_lines(parts), *account.open_lines(tied), *tail],
        told=told,
        short=short_of(hot),
        left=short_of(crowded_now(look, machine)),
    )


def log_clean(job: Job, told: account.Account) -> None:
    """Record a clean that freed space, for the ``LOG`` line (keyword: log-line).

    Args:
        job: the job.
        told: what the clean did.
    """
    if not job.option.dry:
        log = job.look.settings.slots.log
        freed = logline.Freed(
            who=job.option.command, size=sum(told.freed), heads=told.heads
        )
        logline.record_clean(log, freed, job.machine.now)


def told_of(
    job: Job, parts: Sequence[Part], tied: Sequence[local.Worktree]
) -> account.Account:
    """What the clean did, to be told.

    Args:
        job: the job.
        parts: what each kind of cleaning did.
        tied: the worktrees with an open PR.

    Returns:
        The account.
    """
    return account.Account(
        dry=job.option.dry,
        hot=job.hot,
        percent=job.look.clean.pressure_percent,
        minimum=job.look.clean.min_free_gib,
        freed=[part.freed for part in parts],
        kept=[each for part in parts for each in part.kept],
        tied=tied,
        heads=[each for part in parts for each in part.heads],
        measure=lambda path: job.machine.fs.inspect(path).size,
    )
