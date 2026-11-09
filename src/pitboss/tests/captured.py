"""The one place a test runs a command and keeps what it printed (keyword: captured-run).

A failure that shows a status and nothing else is a puzzle (pitboss#402), so a
command that fails here raises with the command, the exit status and what it
wrote. This module imports nothing of pitboss, so the helpers of ``fakes`` and
``repositories`` that use it add no layer to the import graph.
"""

import os
import subprocess
from collections.abc import Mapping, Sequence


class Failed(subprocess.CalledProcessError):
    """A command that exited with a status, shown with the command and its output."""

    def __str__(self) -> str:
        """The command, the status and the output.

        Returns:
            The text of the failure.
        """
        return described(
            subprocess.CompletedProcess(
                self.cmd, self.returncode, self.stdout, self.stderr
            )
        )


def described(done: "subprocess.CompletedProcess[str]") -> str:
    """The command, the exit status and the output of a finished command.

    Args:
        done: the finished process.

    Returns:
        One text with the three, for the message of a failure.
    """
    return (
        f"command {done.args!r} exited {done.returncode}; "
        f"stderr: {done.stderr!r}; stdout: {done.stdout!r}"
    )


def run(
    command: Sequence[str],
    *,
    check: bool = True,
    merge: bool = False,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> "subprocess.CompletedProcess[str]":
    """Run a command and keep its output.

    Args:
        command: the command line.
        check: whether a nonzero exit status raises ``Failed``.
        merge: whether standard error is joined to standard output.
        cwd: where it runs; None is the directory of the test process.
        env: its environment; None is this process's.

    Returns:
        The finished process, with its arguments, status and output.

    Raises:
        Failed: for a nonzero exit status when ``check`` is set.
    """
    done = subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if merge else subprocess.PIPE,
        text=True,
        check=False,
    )
    if check and done.returncode:
        raise Failed(done.returncode, done.args, done.stdout, done.stderr)
    return done
