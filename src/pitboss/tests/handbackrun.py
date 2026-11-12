"""Running ``hand-back-check`` against a world and a directory of processes."""

import os
import pathlib
from typing import Mapping

from . import fakes, world
from .fakes import write

HANDED = "Deviations: none\n"


def saved(handback: str) -> str:
    """Save a hand-back to a file.

    Args:
        handback: the hand-back text.

    Returns:
        The file's name.
    """
    path = fakes.directory() / "handback.txt"
    path.write_text(handback, encoding="utf-8")
    return path.as_posix()


def processes(top: pathlib.Path, working: Mapping[int, pathlib.Path]) -> pathlib.Path:
    """A directory of process entries: a shell (5, child of 4) and the jobs.

    Args:
        top: where to make it.
        working: the working directory of each job by process id.

    Returns:
        The directory.
    """
    proc = top / "proc"
    own = [(4, 1, top), (5, 4, top)]
    for pid, parent, cwd in (*own, *[(p, 4, w) for p, w in working.items()]):
        entry = proc / str(pid)
        entry.mkdir(parents=True)
        write(entry / "stat", f"{pid} (name) S {parent} 0\n")
        (entry / "cmdline").write_bytes(b"sleep\x00100\x00")
        os.symlink(cwd, entry / "cwd")
    (proc / "self").mkdir()
    return proc


def hand_back(
    here: world.World, proc: pathlib.Path, *more: str, text: str = HANDED
) -> world.Result:
    """Run ``hand-back-check`` on a deviations file against a process directory.

    Args:
        here: the world.
        proc: the directory of process entries.
        *more: more arguments.
        text: the hand-back.

    Returns:
        What it printed and its status.
    """
    args = ("hand-back-check", saved(text), "--config", here.config)
    return world.invoke(here, *args, "--processes", str(proc), *more)


def no_jobs() -> pathlib.Path:
    """A directory of process entries with no job running.

    Returns:
        The directory.
    """
    return processes(fakes.directory(), {})
