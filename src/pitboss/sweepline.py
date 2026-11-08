"""The runner-pressure line of the sweep: it reads the record and writes its look."""

import datetime
import functools
import pathlib
from typing import Callable, Iterable, Sequence

from .markers import Marker
from . import (
    blockedline,
    config,
    ghapi,
    holds,
    exempt,
    ledger,
    pulls,
    pullread,
    queue,
    report,
    slotidle,
    slotlog,
    unreadableline,
    work,
)


def slots(
    book: ledger.Ledger,
    open_now: Sequence[pulls.Read],
    offer: work.Offered,
) -> None:
    """Print the withheld-tickets line, the hold, blocked and free-slots lines.

    Args:
        book: the ledger.
        open_now: the open PRs, read or not.
        offer: the queued work and the tickets held back (``offering.offered``).
    """
    unreadableline.print_withheld(open_now)
    for line in holds.sweep_lines(offer.standing):
        print(line)
    for item in offer.blocked:
        print(blockedline.line(item.reference, item.blocker))
    report.print_free_slots(book, len(offer.items))


def idle(
    book: ledger.Ledger, offer: work.Offered, log: pathlib.Path, now: datetime.datetime
) -> None:
    """Print the ``SLOT IDLE`` lines, while work is queued.

    Args:
        book: the ledger.
        offer: the queued work (``offering.offered``).
        log: the slot log, which tells how long a slot stayed empty.
        now: the time now.
    """
    if offer.items:
        for line in slotidle.lines(book, slotlog.read(log), now):
            print(line)


def pressure(
    github: ghapi.GitHub,
    runs: Iterable[queue.QueueRun],
    runners: config.Runners,
    now: datetime.datetime,
) -> str:
    """Look at the runners and say the pressure line, and who is exempt from it.

    Under a hold the line is followed by one that says ``pitboss is exempt from
    holds`` (keyword: pitboss-exempt, pitboss#113).

    Args:
        github: the API.
        runs: the runs of the repositories that share the runners.
        runners: the repositories, the record and the quiet period.
        now: the time now.

    Returns:
        The lines.
    """
    said = looked(github, runs, runners, now)
    held = any(
        each.startswith(Marker.RUNNER_PRESSURE.text) for each in said.split("\n")
    )
    return "\n".join([said, exempt.sweep_saying(runners.exempt)] if held else [said])


def looked(
    github: ghapi.GitHub,
    runs: Iterable[queue.QueueRun],
    runners: config.Runners,
    now: datetime.datetime,
) -> str:
    """Look at the runners and say the pressure line.

    A record that cannot be read does not stop the sweep: the line says the
    quiet period cannot be told, which is a hold.

    Args:
        github: the API.
        runs: the runs of the repositories that share the runners.
        runners: the repositories, the record and the quiet period.
        now: the time now.

    Returns:
        The line.
    """
    if not runners.held:
        return report.no_hold_line()
    measured = measure(github, runs, runners, now)
    if not isinstance(measured, tuple):
        return report.unreadable_record_line(measured)
    jobs, found = measured
    if not jobs.unread:
        return report.seen_line(found)
    return partial_pressure(jobs, found.owed)


def measure(
    github: ghapi.GitHub,
    runs: Iterable[queue.QueueRun],
    runners: config.Runners,
    now: datetime.datetime,
) -> tuple[queue.Jobs, queue.Seen] | str | int | None:
    """Count the jobs waiting and what the quiet period owes, and record the look.

    The look is written to the record (keyword: quiet-period, pitboss#215), so
    the quiet period can end with no one running ``pressure`` by hand.

    Args:
        github: the API.
        runs: the runs of the repositories that share the runners.
        runners: the repositories, the record and the quiet period.
        now: the time now.

    Returns:
        The jobs and what the look showed, or the exit code of a record that
        cannot be read or written.
    """
    try:
        jobs = queue.count_jobs(github, runs)
        found = queue.count(jobs, runners, now)
        queue.note_look(jobs, runners, now)
        return jobs, found
    except SystemExit as unreadable:
        return unreadable.code


def partial_pressure(jobs: queue.Jobs, owed: int) -> str:
    """The pressure lines when a queue run's jobs call failed.

    A count known to be incomplete is no free runner (keyword:
    unreadable-pull): the line holds, as a record that cannot be read does.

    Args:
        jobs: what the look saw, with the runs it could not read.
        owed: the quiet minutes still owed.

    Returns:
        The lines: each unreadable run, then the pressure line.
    """
    count = len(jobs.unread)
    named = [unreadableline.unreadable_line(each) for each in jobs.unread]
    tail = f"partial: {count} queue run(s) not counted"
    if jobs.waiting or owed:
        return "\n".join([*named, f"{report.quiet_line(jobs.waiting, owed)}; {tail}"])
    head = f"{Marker.RUNNER_PRESSURE.text}: {tail}, so a free runner cannot be told"
    return "\n".join([*named, f"{head}; {report.HOLD_ACTIONS}"])


def open_pulls(
    github: ghapi.GitHub,
    settings: config.Config,
    now: datetime.datetime,
    runs: Callable[[], Sequence[queue.QueueRun]],
) -> Sequence[pulls.Read]:
    """Read every open PR the configuration names.

    Args:
        github: the API.
        settings: the configuration.
        now: the time now.
        runs: reads the queue runs of the repositories that share the runners,
            when an undraft needs them.

    Returns:
        The PRs, a PR whose API call failed as an ``Unreadable``.
    """
    return pullread.read_each(
        github, settings, undraft_check(github, settings, now, runs)
    )


def undraft_check(
    github: ghapi.GitHub,
    settings: config.Config,
    now: datetime.datetime,
    runs: Callable[[], Sequence[queue.QueueRun]],
) -> Callable[[], bool]:
    """The question whether an undraft is allowed, asked once for the run.

    Args:
        github: the API.
        settings: the configuration.
        now: the time now.
        runs: reads the queue runs of the repositories that share the runners.

    Returns:
        The question.
    """
    ask = functools.partial(clear, github, runs, settings.runners, now)
    return functools.cache(ask)


def looked_pulls(
    github: ghapi.GitHub,
    settings: config.Config,
    now: datetime.datetime,
    runs: Callable[[], Sequence[queue.QueueRun]],
) -> Sequence[pulls.Read]:
    """Look at the runners, record the look, and read every open PR.

    ``next`` makes this look even when no PR needs an undraft (keyword:
    quiet-period, pitboss#215); the PRs are asked about it from the same look.

    Args:
        github: the API.
        settings: the configuration.
        now: the time now.
        runs: reads the queue runs of the repositories that share the runners.

    Returns:
        The PRs, a PR whose API call failed as an ``Unreadable``.
    """
    undraft = undraft_check(github, settings, now, runs)
    undraft()  # the look, whether or not a PR asks
    return pullread.read_each(github, settings, undraft)


def clear(
    github: ghapi.GitHub,
    runs: Callable[[], Sequence[queue.QueueRun]],
    runners: config.Runners,
    now: datetime.datetime,
) -> bool:
    """Whether the runners allow a CI-triggering action now; the look is recorded.

    No job waits for a runner and the quiet period is over, as ``pitboss
    pressure`` would say. A look that cannot be read (the record, a queue
    run's jobs) is a hold (keyword: quiet-period). A configuration with no
    ``[runners]`` table never holds.

    Args:
        github: the API.
        runs: reads the runs of the repositories that share the runners.
        runners: the repositories, the record and the quiet period.
        now: the time now.

    Returns:
        True when an undraft may be done now.
    """
    if not runners.held:
        return True
    measured = measure(github, runs(), runners, now)
    if not isinstance(measured, tuple):
        return False
    jobs, found = measured
    return not (jobs.waiting or jobs.unread or found.owed)
