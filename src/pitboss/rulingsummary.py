"""The daily summary of the Opus rulings (keyword: ruling-summary, pitboss#237).

The owner's standing ruling (2026-11-04): once a day, every Opus ruling is
summarized, each with a suggested mitigation. The summary is a markdown
artifact the orchestrator writes; the record is a text file of one line for
each summary, its ISO time with an offset, appended by ``pitboss
ruling-summary``. The day is the Pacific day (``America/Los_Angeles``).
"""

import dataclasses
import datetime
import pathlib
import subprocess
import zoneinfo
from typing import AbstractSet, Sequence

from . import flowstate, ghapi, shapes
from .markers import Marker

ZONE = zoneinfo.ZoneInfo("America/Los_Angeles")
RECORD_NAME = "pitboss-ruling-summaries.log"
COMMAND = "uvx pitboss ruling-summary"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ruling:
    """One Opus ruling comment, on an open, merged or closed PR or on an issue.

    Attributes:
        when: when it was written.
        url: its address, empty when the API gave none.
    """

    when: datetime.datetime
    url: str = ""


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
) -> Sequence[Ruling]:
    """The trusted Opus ruling comments among the comments of a repository.

    Args:
        comments: issue comments, which are the comments of PRs too.
        trusted: the author associations whose comments count.

    Returns:
        Each ruling comment whose time can be read.
    """
    found: list[Ruling] = []
    for each in comments:
        time = _time(each.created_at)
        if (
            time
            and flowstate.is_ruling(each.body)
            and each.author_association in trusted
        ):
            found.append(Ruling(when=time, url=each.url))
    return found


def since(text: str) -> str:
    """The time from which the comments of a repository are asked for.

    Args:
        text: the record of the summaries.

    Returns:
        The last summary's UTC time as GitHub's ``since`` takes it, or empty
        when none is recorded.
    """
    last = max(recorded(text), default=None)
    if last is None:
        return ""
    return last.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def recorded_today(text: str, now: datetime.datetime) -> bool:
    """Whether a summary is recorded for the Pacific day of now.

    Args:
        text: the record of the summaries.
        now: the time now.

    Returns:
        True when one is.
    """
    return any(pacific_day(each) == pacific_day(now) for each in recorded(text))


def due(
    rulings: Sequence[Ruling], text: str, now: datetime.datetime
) -> Sequence[Ruling]:
    """The rulings that wait for a summary.

    Args:
        rulings: when the Opus rulings were written.
        text: the record of the summaries.
        now: the time now.

    Returns:
        The rulings dated since the last summary, or none when a summary is
        recorded for the Pacific day of now.
    """
    if recorded_today(text, now):
        return []
    last = max(recorded(text), default=None)
    return [each for each in rulings if last is None or each.when > last]


def line(waiting: Sequence[Ruling], config: str, path: pathlib.Path) -> str:
    """The sweep line for rulings that wait for a summary.

    Args:
        waiting: the rulings, each named by its address.
        config: the configuration argument of the sweep.
        path: the file that records the summaries.

    Returns:
        The line.
    """
    named = ", ".join(each.url for each in waiting if each.url)
    where = f" ({named})" if named else ""
    return (
        f"{Marker.OPUS_RULINGS_DAILY.text}: {len(waiting)} Opus ruling"
        f" comment(s){where} on open, merged or closed PRs or on issues since"
        " the last summary and none recorded for today (Pacific day); write the"
        " summary of every Opus ruling of the day, each with a suggested"
        " mitigation, as a markdown artifact for the owner, then record it with"
        f" `{COMMAND} {config}` (it appends the time to {path})"
    )


def unreadable_line(failure: subprocess.CalledProcessError) -> str:
    """The sweep line when the comments of the repositories cannot be read.

    Args:
        failure: the failed ``gh api`` run.

    Returns:
        The line.
    """
    return (
        f"{Marker.OPUS_RULINGS_DAILY.text}: the Opus rulings cannot be counted:"
        f" the {ghapi.call_of(failure)} call failed ({ghapi.status_of(failure)});"
        " read the comments of the day by hand and summarize them"
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
