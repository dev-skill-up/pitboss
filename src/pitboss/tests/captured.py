"""The one place a test runs a command and keeps its output (keyword: captured-run).

A failure that shows a status and nothing else is a puzzle (pitboss#402), so a
command that fails here raises with the command, the exit status and what it
wrote. This module imports nothing of pitboss, so the helpers of ``fakes`` and
``repositories`` that use it add no layer to the import graph.
"""

import os
import subprocess
from collections.abc import Mapping, Sequence

Environment = Mapping[str, str] | None
Directory = str | os.PathLike[str] | None


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


def started(
    command: Sequence[str], errors: int, cwd: Directory, env: Environment
) -> "subprocess.CompletedProcess[str]":
    """Run a command and keep its output, whatever its status.

    Args:
        command: the command line.
        errors: ``subprocess.PIPE`` to keep its error output apart,
            ``subprocess.STDOUT`` to join it to the standard output.
        cwd: where it runs; None is the directory of the test process.
        env: its environment; None is this process's.

    Returns:
        The finished process, with its arguments, status and output.
    """
    return subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=errors,
        text=True,
        check=False,
    )


def finished(
    command: Sequence[str], *, cwd: Directory = None, env: Environment = None
) -> "subprocess.CompletedProcess[str]":
    """Run a command and keep its output and its error output, whatever its status.

    Args:
        command: the command line.
        cwd: where it runs; None is the directory of the test process.
        env: its environment; None is this process's.

    Returns:
        The finished process, with its arguments, status and output.
    """
    return started(command, subprocess.PIPE, cwd, env)


def merged(
    command: Sequence[str], *, cwd: Directory = None, env: Environment = None
) -> "subprocess.CompletedProcess[str]":
    """Run a command and keep its output with its error output joined to it.

    Args:
        command: the command line.
        cwd: where it runs; None is the directory of the test process.
        env: its environment; None is this process's.

    Returns:
        The finished process, whatever its status.
    """
    return started(command, subprocess.STDOUT, cwd, env)


def run(
    command: Sequence[str], *, cwd: Directory = None, env: Environment = None
) -> "subprocess.CompletedProcess[str]":
    """Run a command that must succeed.

    Args:
        command: the command line.
        cwd: where it runs; None is the directory of the test process.
        env: its environment; None is this process's.

    Returns:
        The finished process, which exited 0.

    Raises:
        subprocess.CalledProcessError: for any other status, caused by an error
            that says the command, the status and what it wrote.
    """
    done = finished(command, cwd=cwd, env=env)
    if done.returncode:
        raise subprocess.CalledProcessError(
            done.returncode, done.args, done.stdout, done.stderr
        ) from AssertionError(described(done))
    return done
