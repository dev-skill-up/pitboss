"""Running one command of a Plan (keyword: plan-check, pitboss#192).

``pitboss plan-check`` runs each row of a Plan with ``sh -c`` in a directory, with
a time limit; the output goes to a file that is only measured, and nothing is read
from the terminal. The module is the runner the command and its tests share.
"""

import argparse
import os
import pathlib
import subprocess
import tempfile
import time
from typing import IO

from . import plancheck

QUIET = {
    "check": False,
    "capture_output": False,
    "stdin": subprocess.DEVNULL,
}


def status_in(
    args: argparse.Namespace, directory: pathlib.Path, timeout: int, command: str
) -> tuple[int | str, int]:
    """Run one command line in a directory, with a time limit.

    The output goes to a file that is only measured (a pipe a stray child holds
    open would outlast the limit), and nothing is read from the terminal.

    Args:
        args: the parsed arguments.
        directory: the working directory.
        timeout: the most seconds the command may run.
        command: the command line, for ``sh -c``.

    Returns:
        Its exit status, or the text that says why it did not finish, and how
        many bytes it printed, standard output and error together (keyword:
        evidence-size, pitboss#396).
    """
    with tempfile.TemporaryFile() as output:
        outcome = _started(args, command, (directory, timeout), output)
        # the file's own size, whatever the offset the command left
        return outcome, os.fstat(output.fileno()).st_size


def _started(
    args: argparse.Namespace,
    command: str,
    where: tuple[pathlib.Path, int],
    output: IO[bytes],
) -> int | str:
    directory, timeout = where
    try:
        done = args.safe_run(
            ["sh", "-c", command],
            cwd=directory,
            timeout=timeout,
            stdout=output,
            stderr=subprocess.STDOUT,
            **QUIET,
        )
    except subprocess.TimeoutExpired:
        return f"timed out after {timeout}s"
    except OSError as error:
        return f"cannot start ({error})"
    return int(done.returncode)


def run_in(
    args: argparse.Namespace, directory: pathlib.Path, timeout: int, command: str
) -> plancheck.Run:
    """Run one command line in a directory, and time it.

    Args:
        args: the parsed arguments.
        directory: the working directory.
        timeout: the most seconds the command may run.
        command: the command line, for ``sh -c``.

    Returns:
        What it did.
    """
    started = time.monotonic()
    outcome, printed = status_in(args, directory, timeout, command)
    seconds = time.monotonic() - started
    if isinstance(outcome, str):
        return plancheck.cut_off(outcome, seconds)
    return plancheck.finished(outcome, seconds, printed)
