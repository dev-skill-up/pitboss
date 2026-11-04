"""The daily summary of the Opus rulings (keyword: ruling-summary, pitboss#237).

The owner's standing ruling (2026-11-04): once a day, every Opus ruling is
summarized, each with a suggested mitigation. The summary is a markdown
artifact the orchestrator writes; the record is a text file of one line for
each summary, its ISO time with an offset, appended by ``pitboss
ruling-summary``. The day is the Pacific day (``America/Los_Angeles``).
"""

import datetime
import pathlib
import zoneinfo
from typing import AbstractSet, Sequence

from . import flowstate, shapes
from .markers import Marker

ZONE = zoneinfo.ZoneInfo("America/Los_Angeles")
RECORD_NAME = "pitboss-ruling-summaries.log"
COMMAND = "uvx pitboss ruling-summary"


def record_path(main_clone: pathlib.Path) -> pathlib.Path:
    """The file that records the summaries.

    Args:
        main_clone: the project's main clone.

    Returns:
        The file, in the clone's git directory.
    """
    return main_clone / ".git" / RECORD_NAME


def _time(text: str) -> datetime.datetime | None:
    try:
        time = datetime.datetime.fromisoformat(text.strip())
    except ValueError:
        return None
    return time if time.tzinfo else None


def ruled_at(
    comments: Sequence[shapes.Comment], trusted: AbstractSet[str]
) -> Sequence[datetime.datetime]:
    """When the trusted Opus ruling comments of a PR were written.

    Args:
        comments: the comments of a PR.
        trusted: the author associations whose comments count.

    Returns:
        The time of each ruling comment whose time can be read.
    """
    found: list[datetime.datetime] = []
    for each in comments:
        time = _time(each.created_at)
        if (
            time
            and flowstate.is_ruling(each.body)
            and each.author_association in trusted
        ):
            found.append(time)
    return found


def recorded(text: str) -> Sequence[datetime.datetime]:
    """The summaries a record holds; a line that cannot be read is skipped.

    Args:
        text: the record.

    Returns:
        The time of each summary.
    """
    found: list[datetime.datetime] = []
    for each in text.splitlines():
        time = _time(each)
        if time:
            found.append(time)
    return found


def pacific_day(time: datetime.datetime) -> datetime.date:
    """The Pacific day a time falls on.

    Args:
        time: a time with an offset.

    Returns:
        The day.
    """
    return time.astimezone(ZONE).date()


def due(
    rulings: Sequence[datetime.datetime], text: str, now: datetime.datetime
) -> Sequence[datetime.datetime]:
    """The rulings that wait for a summary.

    Args:
        rulings: when the Opus rulings were written.
        text: the record of the summaries.
        now: the time now.

    Returns:
        The rulings dated since the last summary, or none when a summary is
        recorded for the Pacific day of now.
    """
    done = recorded(text)
    if any(pacific_day(each) == pacific_day(now) for each in done):
        return []
    last = max(done, default=None)
    return [each for each in rulings if last is None or each > last]


def line(count: int, config: str, path: pathlib.Path) -> str:
    """The sweep line for rulings that wait for a summary.

    Args:
        count: how many.
        config: the configuration argument of the sweep.
        path: the file that records the summaries.

    Returns:
        The line.
    """
    return (
        f"{Marker.OPUS_RULINGS_DAILY.text}: {count} Opus ruling comment(s) since"
        " the last summary and none recorded for today (Pacific day); write the"
        " summary of every Opus ruling of the day, each with a suggested"
        " mitigation, as a markdown artifact for the owner, then record it with"
        f" `{COMMAND} {config}` (it appends the time to {path})"
    )


def note(path: pathlib.Path, now: datetime.datetime) -> str:
    """Record a summary.

    Args:
        path: the record file.
        now: the time of the summary.

    Returns:
        What to tell the person who recorded it.

    Raises:
        SystemExit: when the file cannot be read or written.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        text = ""
    except OSError as failure:
        raise SystemExit(f"cannot read the ruling summary record {path}: {failure}")
    start = "\n" if text and not text.endswith("\n") else ""
    try:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(f"{start}{now.isoformat(timespec='seconds')}\n")
    except OSError as failure:
        raise SystemExit(f"cannot write the ruling summary record {path}: {failure}")
    return f"recorded the Opus ruling summary of {pacific_day(now)} in {path}"
