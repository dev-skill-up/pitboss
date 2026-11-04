"""The sweep's OPUS RULINGS DAILY line (keyword: ruling-summary, pitboss#237)."""

import datetime
from typing import Sequence

from . import config, pulls, rulingsummary


def lines(
    settings: config.Config,
    name: str,
    read: Sequence[pulls.Read],
    now: datetime.datetime,
) -> Sequence[str]:
    """The line for Opus rulings that wait for the day's summary.

    Args:
        settings: the configuration.
        name: the configuration argument the sweep was given.
        read: the open PRs, read or not.
        now: the time now.

    Returns:
        One line, or none when no ruling waits or the day's summary is recorded.
    """
    path = rulingsummary.record_path(settings.project.main_clone)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    rulings = [
        each for pull in pulls.readable(read) for each in pull.unreadable.rulings
    ]
    waiting = rulingsummary.due(rulings, text, now)
    return [rulingsummary.line(len(waiting), name, path)] if waiting else []
