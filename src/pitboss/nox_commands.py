"""The ``nox`` command: the local check of a worker (pitboss#210)."""

import argparse
import functools
import subprocess
import sys
import time
from typing import Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, expansion, noxcheck


def run_command(args: argparse.Namespace, command: Sequence[str]) -> expansion.Outcome:
    """Run one command line, standard error joined to standard output.

    Args:
        args: the parsed arguments.
        command: the command line.

    Returns:
        The exit status and what it printed.
    """
    done = args.safe_run(
        list(command),
        check=False,
        capture_output=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return expansion.Outcome(status=done.returncode, output=done.stdout)


@ENTRY_DATA.register(
    add_argument(
        "modules",
        nargs="*",
        help="test modules (after --) for the tests session, such as"
        " pitboss.tests.test_gates; all the tests when none",
    ),
    name="nox",
)
def nox(args: argparse.Namespace) -> None:
    """Run the skills, the tests of one Python version, lint and mypy.

    Each runs as ``nox -r -s SESSION``, in that order, and the first that fails
    stops the rest and exits 1 with its output. One line is printed for each
    session that ran, and on success a line says CI's ``Run Nox`` step is the
    proof of the whole suite. No other session runs: docs, dry_release and the
    other Python versions are CI's.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 when a session fails.
    """
    ran = noxcheck.run_sessions(
        functools.partial(run_command, args), time.monotonic, args.modules
    )
    for each in ran:
        print(noxcheck.line_of(each))
    failed = ran[-1].outcome
    if failed.status:
        sys.stdout.write(failed.output)
        raise SystemExit(1)
    print(noxcheck.PROOF)
