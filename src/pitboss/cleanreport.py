"""A sweep's clean and the report it makes: the lines and the ``DISK PRESSURE`` facts.

The clean is aggressive over ``[clean] pressure_percent`` used and under
``[clean] min_free_gib`` free alike (pitboss#205); the report says which file
systems were short of free space before the clean and which still are after it.
"""

import functools
from typing import Sequence

from . import account, autoclean, cleanheader, dead, worktrees
from . import machine as machines
from .machine import Crowded, Machine


def crowded_now(look: dead.Look, machine: Machine) -> Sequence[Crowded]:
    """The file systems that are crowded: over the percent or short of free space.

    Args:
        look: what to look at and keep.
        machine: the machine.

    Returns:
        The file systems; any makes the cleaning aggressive.
    """
    clean = look.clean
    return machines.find_crowded(
        machine,
        autoclean.paths_watched(look),
        clean.pressure_percent,
        clean.min_free_gib,
    )


def run_parts(job: autoclean.Job) -> tuple[Sequence[autoclean.Part], str]:
    """Do each kind of cleaning, and total what it removed.

    Args:
        job: the job.

    Returns:
        What each kind did, and the totals line (the paths removed, the bytes
        and the free space of the workspace before and after).
    """
    use = functools.partial(job.machine.usage, job.look.settings.project.workspace)
    before = use()
    parts = autoclean.all_parts(job)
    gone = [each for part in parts for each in part.gone]
    return parts, account.totals(gone, job.option.dry, before, use())


def parts_lines(parts: Sequence[autoclean.Part]) -> Sequence[str]:
    """What the kinds of cleaning print, in order.

    Args:
        parts: what each kind did.

    Returns:
        Their lines.
    """
    return [text for part in parts for text in part.lines]


def short_of(found: Sequence[Crowded]) -> Sequence[Crowded]:
    """The crowded file systems that have less than the minimum free space.

    Args:
        found: the crowded file systems.

    Returns:
        Those of them.
    """
    return [each for each in found if each.short]


def clean_report(
    look: dead.Look, machine: Machine, option: autoclean.Option
) -> account.Report:
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
    job = autoclean.Job(look=look, machine=machine, option=option, hot=hot)
    parts, totals = run_parts(job)
    tied = worktrees.tied_to_open_pr(look) if hot else []
    told = autoclean.told_of(job, parts, tied)
    return account.Report(
        lines=[
            cleanheader.header(hot, look.clean),
            *parts_lines(parts),
            *account.open_lines(tied),
            cleanheader.never_line(look),
            totals,
            *account.lines(told),
        ],
        told=told,
        short=short_of(hot),
        left=short_of(crowded_now(look, machine)),
    )
