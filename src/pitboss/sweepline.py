"""The runner-pressure line of the sweep: it reads the record and writes nothing."""

import datetime
from typing import Callable, Iterable, Sequence

from .markers import Marker
from . import (
    config,
    ghapi,
    ledger,
    pulls,
    queue,
    report,
    unreadableline,
    work,
)


def slots(
    github: ghapi.GitHub,
    settings: config.Config,
    book: ledger.Ledger,
    open_now: Sequence[pulls.Read],
) -> None:
    """Print the withheld-tickets line and the free-slots line.

    Args:
        github: the API.
        settings: the configuration.
        book: the ledger.
        open_now: the open PRs, read or not.
    """
    unreadableline.print_withheld(open_now)
    queued = work.queued(open_now, github, settings, book)
    report.print_free_slots(book, len(queued))


def pressure(
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
    try:
        jobs = queue.count_jobs(github, runs)
        owed = queue.owed(jobs, runners, now)
    except SystemExit as unreadable:
        return report.unreadable_record_line(unreadable.code)
    if not jobs.unread:
        return report.quiet_line(jobs.waiting, owed)
    return partial_pressure(jobs, owed)


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


def clear(
    github: ghapi.GitHub,
    runs: Callable[[], Sequence[queue.QueueRun]],
    runners: config.Runners,
    now: datetime.datetime,
) -> bool:
    """Whether the runners allow a CI-triggering action now; nothing is written.

    No job waits for a runner and the quiet period is over, as ``pitboss
    pressure`` would say. A look that cannot be read (the record, a queue
    run's jobs) is a hold (keyword: quiet-period).

    Args:
        github: the API.
        runs: reads the runs of the repositories that share the runners.
        runners: the repositories, the record and the quiet period.
        now: the time now.

    Returns:
        True when an undraft may be done now.
    """
    try:
        jobs = queue.count_jobs(github, runs())
        owed = queue.owed(jobs, runners, now)
    except SystemExit:
        return False
    return not (jobs.waiting or jobs.unread or owed)
