"""The ``nox`` command: the local check of a worker (pitboss#210)."""

import argparse
import functools
import subprocess
import sys
import time
from typing import Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, expansion, noxcheck, selectdiff, testselect

HAND_CHOSEN = "test-selection {} test modules named on the command line"
ALL_CHOSEN = "test-selection --all: every test module"


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


def planned(
    args: argparse.Namespace, runner: noxcheck.Runner
) -> tuple[Sequence[str], Sequence[str], Sequence[noxcheck.Session]]:
    """Decide which tests the tests session runs.

    Args:
        args: the parsed arguments.
        runner: runs a command line (git, to find the diff).

    Returns:
        The lines to print, the test modules (none: all of them) and the
        sessions to run (without the tests session when the diff reaches no test).
    """
    everything = tuple(noxcheck.Session)
    if args.modules:
        named = HAND_CHOSEN.format(len(args.modules))
        return [named, testselect.NOT_CHECKED], args.modules, everything
    if args.all:
        return [ALL_CHOSEN], [], everything
    lines, selection = selectdiff.choose(runner)
    reached = selection.everything or selection.chosen
    return (
        lines,
        sorted(selection.chosen),
        everything if reached else noxcheck.WITHOUT_TESTS,
    )


def show(ran: Sequence[noxcheck.Step]) -> None:
    """Print a line for each session that ran, and the output of one that failed.

    Args:
        ran: the sessions that ran; a failed one is the last.

    Raises:
        SystemExit: 1 when the last session failed.
    """
    for each in ran:
        print(noxcheck.line_of(each))
        # a failed session's whole output follows below, timing included
        if not each.outcome.status:
            for timing in noxcheck.timing_of(each):
                print(timing)
    failed = ran[-1].outcome
    if failed.status:
        sys.stdout.write(failed.output)
        raise SystemExit(1)
    print(noxcheck.PROOF)


@ENTRY_DATA.register(
    add_argument(
        "modules",
        nargs="*",
        help="test modules (after --) for the tests session, such as"
        " pitboss.tests.test_gates. With none, the tests session runs the test"
        " modules the diff against the merge base of origin/main can affect: a"
        " changed test module, the test modules that import a changed module of"
        " src/pitboss directly or through others, and those that name a command"
        " (as a string) that a changed module registers. It prints each with"
        " the changed files that reach it, how many it left out, and that"
        " coverage of the left-out tests is not checked (CI's Run Nox step"
        " checks the whole suite). Every test runs when a changed file is not"
        " a module of src/pitboss (a doc, a skill, a config, noxfile.py,"
        " pyproject.toml, a data file), when a shared module of the tests is"
        " changed or deleted, when a module is deleted, when a file cannot be"
        " parsed and when git cannot say the diff; no test runs when the diff"
        " reaches none.",
    ),
    add_argument(
        "--all",
        action="store_true",
        default=False,
        help="run every test, whatever the diff is",
    ),
    name="nox",
)
def nox(args: argparse.Namespace) -> None:
    """Run the sessions of ``noxcheck.Session``, in their order.

    Each runs as ``nox -r -s SESSION`` (the rule is ``brieftextwork.NOX``), and
    a failing session stops the rest and exits 1 with its output. One line is
    printed for each session that ran, with the ``test-timing`` lines of a
    session that passed (pitboss#324), and on success a line says CI's
    ``Run Nox`` step is the proof of the whole suite. No other session runs:
    docs, dry_release and the other Python versions are CI's. The tests session
    runs the tests the diff can affect (``testselect``, ``selectdiff``,
    pitboss#331), printed first with the reason; ``--all`` or any module named
    replaces that choice.

    Args:
        args: the parsed arguments.
    """
    runner = functools.partial(run_command, args)
    lines, modules, sessions = planned(args, runner)
    for each in lines:
        print(each)
    show(noxcheck.run_sessions(runner, time.monotonic, modules, sessions))
