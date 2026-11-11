"""How long the process took to start (keyword: timing-lines, pitboss#443).

``uvx pitboss`` resolves and installs before Python runs, and Python imports
the package before a command starts. Neither is in a command's own clock, so
the breakdown reads them from the operating system's own record of when the
process (and the ``uv`` that launched it) began. Where ``/proc`` is not there
(macOS), the start-up is not known.
"""

import os
from typing import Callable

LAUNCHERS = frozenset({"uv", "uvx"})
STAT_FIELD_PARENT = 1
STAT_FIELD_START = 19  # field 22 of proc(5), counted after the ")" of the name

Read = Callable[[str], str]


def read_file(path: str) -> str:
    """Read a file of ``/proc``.

    Args:
        path: the file.

    Returns:
        Its text.
    """
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def _beginning(read: Read, pid: str) -> tuple[str, int]:
    # the parent and the start of a process, in clock ticks since the boot
    after = read(f"/proc/{pid}/stat").rsplit(")", 1)[1].split()
    return after[STAT_FIELD_PARENT], int(after[STAT_FIELD_START])


def age(read: Read = read_file, hertz: int | None = None) -> float | None:
    """The seconds since this process began, or since the ``uv`` that made it did.

    Args:
        read: reads a file of ``/proc`` (a test gives its own).
        hertz: the clock ticks in a second, None for the system's.

    Returns:
        The seconds, None when the system does not say.
    """
    ticks_per_second = hertz or os.sysconf("SC_CLK_TCK")
    try:
        uptime = float(read("/proc/uptime").split()[0])
        parent, began = _beginning(read, "self")
        if read(f"/proc/{parent}/comm").strip() in LAUNCHERS:
            began = _beginning(read, parent)[1]
    except (OSError, ValueError, IndexError):
        return None
    return uptime - began / ticks_per_second
