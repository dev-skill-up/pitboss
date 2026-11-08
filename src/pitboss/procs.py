"""The directories the running processes work in (keyword: clean-container).

A process works in its current directory and in the ``TMPDIR`` it was started
with; ``clean-container`` leaves a tempdir that one of them is in or under
(pitboss#348). Another user's process cannot be looked at and counts for nothing.
"""

import pathlib
from typing import AbstractSet

PROC = pathlib.Path("/proc")


def working_of(process: pathlib.Path) -> AbstractSet[pathlib.Path]:
    """The directories one process works in.

    Args:
        process: its directory under ``/proc``.

    Returns:
        Its current directory and its ``TMPDIR``; none when it cannot be read.
    """
    try:
        here = pathlib.Path((process / "cwd").readlink())
        variables = (process / "environ").read_bytes().split(b"\0")
    except OSError:
        return frozenset()
    tmp = {
        pathlib.Path(one.decode(errors="replace").removeprefix("TMPDIR="))
        for one in variables
        if one.startswith(b"TMPDIR=")
    }
    return {here, *tmp}


def in_use(proc: pathlib.Path = PROC) -> AbstractSet[pathlib.Path]:
    """The directories the running processes work in.

    Args:
        proc: the directory of the processes (``/proc``).

    Returns:
        The union of what each process works in.
    """
    found: set[pathlib.Path] = set()
    for process in proc.iterdir():
        if process.name.isdigit():
            found |= working_of(process)
    return found
