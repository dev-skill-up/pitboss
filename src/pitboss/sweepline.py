"""The runner-pressure line of the sweep: it reads the record and writes its look."""

import datetime
import functools
import threading
from typing import Callable, Iterable, Sequence

from . import config, exempt, ghapi, holdscope, queue, report, unreadableline
from .markers import Marker

# the run's one look: the jobs and what it showed, or an unreadable record's code
_Got = tuple[queue.Jobs, queue.Seen] | str | int | None
Look = Callable[[], _Got]


def pressure(measured: Look, runners: config.Runners) -> str:
    """Look at the runners and say the pressure line, and who is exempt from it.

    Under a hold the line is followed by one that says ``pitboss is exempt from
    holds`` (keyword: pitboss-exempt, pitboss#113).

    Args:
        measured: the run's one look at the runners (``runners_look``).
        runners: the repositories, the record and the quiet period.

    Returns:
        The lines.
    """
    said = looked(measured, runners)
    held = any(
        each.startswith(Marker.RUNNER_PRESSURE.text) for each in said.split("\n")
    )
    more = [exempt.sweep_saying(runners.exempt), holdscope.saying(runners)]
    return "\n".join([said, *more] if held else [said])


def looked(measured: Look, runners: config.Runners) -> str:
    """Look at the runners and say the pressure line.

    A record that cannot be read does not stop the sweep: the line says the
    quiet period cannot be told, which is a hold.

    Args:
        measured: the run's one look at the runners (``runners_look``).
        runners: the repositories, the record and the quiet period.

    Returns:
        The line.
    """
    if not runners.held:
        return report.no_hold_line()
    got = measured()
    if not isinstance(got, tuple):
        return report.unreadable_record_line(got)
    jobs, found = got
    if not jobs.unread:
        return report.seen_line(found)
    return partial_pressure(jobs, found.owed)


def _measure(
    github: ghapi.GitHub,
    runs: Callable[[], Iterable[queue.QueueRun]],
    runners: config.Runners,
    now: datetime.datetime,
) -> _Got:
    # count the jobs and what the quiet period owes, and record the look (keyword:
    # quiet-period, pitboss#215): the quiet period ends with no one running pressure
    try:
        jobs = queue.count_jobs(github, runs())
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


def runners_look(
    github: ghapi.GitHub,
    runs: Callable[[], Sequence[queue.QueueRun]],
    runners: config.Runners,
    now: datetime.datetime,
) -> Look:
    """The run's one look at the runners: made on the first ask, recorded once.

    The undraft check of each pull request and the sweep's pressure line ask
    the same look (keyword: one-path, quiet-period), so the record's first look
    is said by the line that reads it.

    Args:
        github: the API.
        runs: reads the queue runs of the repositories that share the runners.
        runners: the repositories, the record and the quiet period.
        now: the time now.

    Returns:
        The look.
    """
    ask = functools.cache(functools.partial(_measure, github, runs, runners, now))
    turn = threading.Lock()

    def once() -> _Got:
        with turn:  # the look is made once, though PRs and the run both ask
            return ask()

    return once


def clear(measured: Look, runners: config.Runners) -> bool:
    """Whether the runners allow a CI-triggering action now; the look is recorded.

    No job waits for a runner and the quiet period is over, as ``pitboss
    pressure`` would say. A look that cannot be read (the record, a queue
    run's jobs) is a hold (keyword: quiet-period). A configuration with no
    ``[runners]`` table never holds.

    Args:
        measured: the run's one look at the runners (``runners_look``).
        runners: the repositories, the record and the quiet period.

    Returns:
        True when an undraft may be done now.
    """
    if not runners.held:
        return True
    got = measured()
    if not isinstance(got, tuple):
        return False
    jobs, found = got
    return not (jobs.waiting or jobs.unread or found.owed)
