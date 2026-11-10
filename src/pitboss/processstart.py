"""When the Claude process of the session started (keyword: slots-watch, pitboss#415).

An agent mid-turn whose transcript was last written before this time was held by a
process that is gone, so it cannot be running.
"""

import datetime
import os
import subprocess
from typing import Sequence

from .running import Run

LSTART_FORMAT = "%a %b %d %H:%M:%S %Y"
DEPTH = 64


def parse(text: str) -> datetime.datetime:
    """Read the ``ps -o lstart=`` form, in the machine's zone.

    Args:
        text: for example ``Tue Nov 10 02:55:08 2026``.

    Returns:
        The time in UTC.
    """
    local = datetime.datetime.strptime(" ".join(text.split()), LSTART_FORMAT)
    return local.astimezone(datetime.timezone.utc)


def _ask(run: Run, pid: int, *fields: str) -> str | None:
    try:
        done = run(
            ["ps", "-o", ",".join(f"{each}=" for each in fields), "-p", str(pid)]
        )
    except (subprocess.CalledProcessError, OSError):
        return None
    return done.stdout.strip() or None


def of_claude(run: Run, pid: int | None = None) -> datetime.datetime | None:
    """The start time of the nearest ancestor that is the ``claude`` binary.

    Args:
        run: the runner of ``ps``.
        pid: where to start looking; the process itself when None.

    Returns:
        The time in UTC, or None when no ancestor is ``claude`` or ``ps`` cannot say.
    """
    current = os.getpid() if pid is None else pid
    for _ in range(DEPTH):
        words: Sequence[str] = (_ask(run, current, "ppid", "comm") or "").split()
        if len(words) < 2 or not words[0].isdigit():
            return None
        if os.path.basename(words[1]).startswith("claude"):
            began = _ask(run, current, "lstart")
            return parse(began) if began else None
        current = int(words[0])
        if current <= 1:
            return None
    return None
