"""The runner-pressure line of the sweep: it reads the record and writes nothing."""

import datetime
from typing import Iterable

from . import config, ghapi, queue, report


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
        waiting, owed = queue.look(github, runs, runners, now)
    except SystemExit as unreadable:
        return report.unreadable_record_line(unreadable.code)
    return report.quiet_line(waiting, owed)
