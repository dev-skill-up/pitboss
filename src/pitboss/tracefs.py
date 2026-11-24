"""Mount tracefs when it is not mounted, and say so on one line.

tracefs is mounted per boot, and the environment's setup script does not run
after a container restart, so the mount cannot rely on it: the commands a
session runs at a check-in or before a push make it (keyword: tracefs).
"""

import subprocess
import sys

from typing import Protocol, Sequence

from .running import Run

CHECK: Sequence[str] = ("grep", "tracefs", "/proc/mounts")
MOUNT: Sequence[str] = ("mount", "-t", "tracefs", "nodev", "/sys/kernel/tracing")
NOT_RUNNABLE = 127


def status(run: Run, command: Sequence[str]) -> int:
    """Run a command and give its exit status.

    Args:
        run: the runner.
        command: the command line.

    Returns:
        0 when it succeeded, its exit status when it failed, 127 when it
        could not be started (as a shell says).
    """
    try:
        run(command)
    except subprocess.CalledProcessError as failure:
        return failure.returncode
    except OSError:
        return NOT_RUNNABLE
    return 0


def ensure(run: Run) -> str:
    """Mount tracefs unless ``/proc/mounts`` lists it.

    Where there is no ``/proc/mounts`` (macOS, the BSDs) the check fails like
    an unmounted tracefs, the mount is tried, and its failure is the line.

    Args:
        run: the runner (one that runs in a dry run too).

    Returns:
        The line to say: found mounted, mounted, or not mounted with the
        mount's exit status.
    """
    if status(run, CHECK) == 0:
        return "tracefs: found mounted"
    code = status(run, MOUNT)
    if code == 0:
        return "tracefs: mounted"
    return f"tracefs: NOT MOUNTED (mount exit status {code})"


class WithRunner(Protocol):
    """Something that has a runner, as the world a command is given has."""

    @property
    def safe_run(self) -> Run:
        """Return the runner (one that runs in a dry run too)."""


def said(world: WithRunner) -> None:
    """Make the mount and print its line on stderr, with a world's runner.

    Args:
        world: what the command is given.
    """
    say(world.safe_run)


def say(run: Run) -> None:
    """Make the mount and print its line on stderr.

    Args:
        run: the runner (one that runs in a dry run too).
    """
    print(ensure(run), file=sys.stderr)
