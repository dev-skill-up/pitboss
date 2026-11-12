"""The sweep's OPUS RULINGS DAILY line (keyword: ruling-summary, pitboss#237, #239)."""

import datetime
import subprocess
from typing import Sequence

from . import concurrently, config, configrepos, ghapi, parsing, rulingsummary


def _feed(
    github: ghapi.GitHub, settings: config.Config, since: str
) -> Sequence[rulingsummary.Ruling]:
    # The repository's comments of every PR (open, merged or closed) and issue.
    query = f"?since={since}" if since else ""
    repos = configrepos.repositories(settings)
    found = concurrently.each(
        lambda repo: ghapi.pages(
            github, f"repos/{repo.slug}/issues/comments{query}", parsing.comments
        ),
        repos,
    )
    return [
        ruling
        for comments in found
        for ruling in rulingsummary.ruled_at(comments, settings.review.trusted)
    ]


def lines(
    github: ghapi.GitHub,
    settings: config.Config,
    name: str,
    now: datetime.datetime,
) -> Sequence[str]:
    """The line for Opus rulings that wait for the day's summary.

    The rulings are read from the repositories' issue comments since the last
    summary, so a ruling on a merged or closed PR or on an issue counts as one
    on an open PR does.

    Args:
        github: the API.
        settings: the configuration.
        name: the configuration argument the sweep was given.
        now: the time now.

    Returns:
        One line, or none when no ruling waits or the day's summary is recorded.
    """
    path = rulingsummary.record_path(settings.project.main_clone)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if rulingsummary.recorded_today(text, now):
        return []
    try:
        rulings = _feed(github, settings, rulingsummary.since(text))
    except subprocess.CalledProcessError as failure:
        return [rulingsummary.unreadable_line(failure)]
    waiting = rulingsummary.due(rulings, text, now)
    return [rulingsummary.line(waiting, name, path)] if waiting else []


def print_lines(
    github: ghapi.GitHub,
    settings: config.Config,
    name: str,
    now: datetime.datetime,
) -> None:
    """Print the line for Opus rulings that wait for the day's summary.

    Args:
        github: the API.
        settings: the configuration.
        name: the configuration argument the sweep was given.
        now: the time now.
    """
    for text in lines(github, settings, name, now):
        print(text)
