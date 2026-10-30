"""The pressure record: when the runners were looked at, and when a job was queued.

A hold lifts only after a quiet period in which no look saw a hold and no job
was put on the queue (keyword: quiet-period). The record is a text file of one
line for each look or queued job, ``<ISO time with offset> none|hold``,
appended in time order; nothing else is kept.
"""

import dataclasses
import datetime
import enum
import pathlib
from typing import Sequence


class Look(enum.Enum):
    """What a look at the runners, or a queued job, showed.

    Attributes:
        NONE: no queue-run job waited for a runner.
        HOLD: a job waited, or a job was put on the queue.
    """

    NONE = enum.auto()
    HOLD = enum.auto()


WORDS = {Look.NONE: "none", Look.HOLD: "hold"}
LOOKS = {word: look for look, word in WORDS.items()}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Entry:
    """One line of the record.

    Attributes:
        time: when.
        look: what was seen.
    """

    time: datetime.datetime
    look: Look


def read(path: pathlib.Path) -> str:
    """Read the record file, undecodable bytes replaced (they make a bad line).

    A missing file is an empty record; a file that cannot be read stops the
    command, because a quiet period nobody could read is not one that was seen.

    Args:
        path: the file.

    Returns:
        The text, empty when there is no file.

    Raises:
        SystemExit: when the file exists and cannot be read.
    """
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    except OSError as failure:
        raise SystemExit(f"cannot read the pressure record {path}: {failure}")


def append(path: pathlib.Path, text: str) -> None:
    """Append to the record file.

    Args:
        path: the file.
        text: the text.

    Raises:
        SystemExit: when the file cannot be written.
    """
    try:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(text)
    except OSError as failure:
        raise SystemExit(f"cannot write the pressure record {path}: {failure}")


def line(entry: Entry) -> str:
    """The text of an entry, without its newline.

    Args:
        entry: the entry.

    Returns:
        The line.
    """
    return f"{entry.time.isoformat(timespec='seconds')} {WORDS[entry.look]}"


def addition(text: str, entry: Entry) -> str:
    """What to append so the entry is a line of its own.

    A record whose last line was cut short (a write that did not finish) gets a
    newline first, so the new entry is not glued to it.

    Args:
        text: the record as it is.
        entry: the entry.

    Returns:
        The text to append.
    """
    start = "\n" if text and not text.endswith("\n") else ""
    return f"{start}{line(entry)}\n"


def _parse_line(text: str) -> Entry | None:
    fields = text.split()
    if len(fields) != 2:
        return None
    try:
        time = datetime.datetime.fromisoformat(fields[0])
    except ValueError:
        return None
    look = LOOKS.get(fields[1])
    if look is None or time.tzinfo is None:
        return None
    return Entry(time=time, look=look)


def read_entries(text: str, now: datetime.datetime) -> Sequence[Entry]:
    """Read the record, where a line that cannot be read counts as a hold.

    A bad line (not ``<time with offset> none|hold``) may have been a hold, and
    its time is lost, so it is taken as a hold at the time of the next good
    line, or, at the end of the record, at the time of the look being made now;
    it never makes a quiet period that was not seen. Blank lines are not lines.

    Args:
        text: the record.
        now: the time of the look that follows the record.

    Returns:
        The entries in the record's order.
    """
    entries: list[Entry] = []
    bad = 0
    for each in text.splitlines():
        if not each.strip():
            continue
        parsed = _parse_line(each)
        if parsed is None:
            bad += 1
            continue
        entries.extend([Entry(time=parsed.time, look=Look.HOLD)] * bad)
        bad = 0
        entries.append(parsed)
    return [*entries, *[Entry(time=now, look=Look.HOLD)] * bad]


def minutes_remaining(
    entries: Sequence[Entry], quiet_minutes: int, now: datetime.datetime
) -> int:
    """How many whole minutes of quiet are still owed.

    The quiet period runs from the newest hold; where the record has none, from
    its oldest entry, because the runners were not looked at before that.

    Args:
        entries: the record with the look being made last, times known.
        quiet_minutes: the length of the quiet period.
        now: the time now.

    Returns:
        0 when the quiet period is over, else the minutes left, rounded up.
    """
    holds = [each.time for each in entries if each.look is Look.HOLD]
    since = max(holds) if holds else min(each.time for each in entries)
    owed = datetime.timedelta(minutes=quiet_minutes) - (now - since)
    return max(0, -int(-owed.total_seconds() // 60))


def remaining(
    path: pathlib.Path, look: Look, quiet_minutes: int, now: datetime.datetime
) -> int:
    """The quiet minutes owed once a look is added, which is not written.

    Args:
        path: the record file.
        look: what the look at ``now`` shows.
        quiet_minutes: the length of the quiet period.
        now: the time now.

    Returns:
        0 when the quiet period is over, else the minutes left.
    """
    entries = [*read_entries(read(path), now), Entry(time=now, look=look)]
    return minutes_remaining(entries, quiet_minutes, now)


def note(path: pathlib.Path, look: Look, now: datetime.datetime) -> None:
    """Add a look, or a queued job, to the record.

    Args:
        path: the record file.
        look: what it showed.
        now: the time now.
    """
    append(path, addition(read(path), Entry(time=now, look=look)))
