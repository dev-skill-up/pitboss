"""The runner-pressure line of the sweep: it reads the record and writes nothing."""

import datetime
from typing import Iterable, Sequence

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
        line = report.quiet_line(jobs.waiting, queue.owed(jobs, runners, now))
    except SystemExit as unreadable:
        return report.unreadable_record_line(unreadable.code)
    if not jobs.unread:
        return line
    # A queue run whose jobs call failed is not counted (keyword: unreadable-pull).
    named = [unreadableline.unreadable_line(each) for each in jobs.unread]
    partial = f"{line}; partial: {len(jobs.unread)} queue run(s) not counted"
    return "\n".join([*named, partial])
