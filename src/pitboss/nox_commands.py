"""The ``nox`` command: the local check of a worker (pitboss#210)."""

import argparse
import functools
import subprocess
import sys
import time
from typing import Sequence

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    alsotests,
    configsearch,
    diskwatch,
    expansion,
    noxcheck,
    noxgreen,
    selectdiff,
)
from .commandarguments import NOW_ARGUMENT
from .timing import current_time


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
    lines, selection = selectdiff.choose(runner)
    extra = args.also or []
    modules = {*selection.chosen, *(each.module for each in extra)}
    reached = selection.everything or modules
    return (
        [*lines, *alsotests.lines_of(extra, selection)],
        [] if selection.everything else sorted(modules),
        tuple(noxcheck.Session) if reached else noxcheck.WITHOUT_TESTS,
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


def stop_when_short_of_disk(args: argparse.Namespace) -> None:
    """Print the ``DISK`` line and the clean, and exit, when little is free.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 when the working directory's volume has under 5 GiB free.
    """
    refusal = diskwatch.nox_refusal(
        diskwatch.read(args.usage, configsearch.working_directory(args))
    )
    if refusal:
        for each in refusal:
            print(each)
        raise SystemExit(1)


@ENTRY_DATA.register(
    add_argument(
        "--also",
        action="append",
        type=alsotests.also_of,
        default=None,
        metavar="MODULE=REASON",
        help="a test module to run besides the tests selected, with the reason"
        " (refused without one), such as pitboss.tests.test_gates=reads the"
        " file I changed; the output prints it with its reason, and when the"
        " diff did not select it says to file a ticket against the selection's"
        " limitation and prints the pitboss ticket-find command to run first."
        " The tests session runs the test modules the diff against the merge"
        " base of origin/main can affect: a changed test module, the test"
        " modules that import a changed module of src/pitboss directly or"
        " through others, and those that name a command (as a string) that a"
        " changed module registers. It prints each with the changed files that"
        " reach it, how many it left out, and that coverage of the left-out"
        " tests is not checked (CI's Run Nox step checks the whole suite)."
        " Every test runs when a changed file is not a module of src/pitboss"
        " (a doc, a skill, a config, noxfile.py, pyproject.toml, a data file),"
        " when a shared module of the tests is changed or deleted, when a"
        " module is deleted, when a file cannot be parsed and when git cannot"
        " say the diff; no test runs when the diff reaches none.",
    ),
    add_argument(
        "--force",
        action="store_true",
        default=False,
        help="run the sessions on a head that already ran green (without it the"
        " command prints a NOTE with the time of that run and exits 0; run it"
        " before each push and when feedback is needed, not again on one head;"
        " a tree with a change is never skipped).",
    ),
    NOW_ARGUMENT,
    name="nox",
)
def nox(args: argparse.Namespace) -> None:
    """Run the sessions of ``noxcheck.Session``, in their order.

    Before it starts a session it reads the free space of the volume of the
    working directory (``build/nox`` is written there), and under 5 GiB free it
    exits 1, printing the ``DISK`` line of ``next`` and the auto-approved
    ``uvx pitboss clean-container --no-dry-run`` (``diskwatch.nox_refusal``,
    pitboss#346). The tests session empties its ``TMPDIR`` when it is green and
    keeps it when it fails, and a green run that leaves a directory there fails
    naming the test (``test-leak``). Each session runs as ``nox -r -s SESSION``
    (the rule is ``brieftextwork.NOX``), and
    a failing session stops the rest and exits 1 with its output. One line is
    printed for each session that ran, with the ``test-timing`` lines of a
    session that passed (pitboss#324), and on success a line says CI's
    ``Run Nox`` step is the proof of the whole suite. No other session runs:
    docs, dry_release and the other Python versions are CI's. The tests session
    runs the tests the diff can affect (``testselect``, ``selectdiff``,
    pitboss#331), printed first with the reason; a test module added with
    ``--also MODULE=REASON`` runs besides them (``alsotests``). A head that
    already ran green on a clean tree is not run again: a ``NOTE`` with the
    time of that run is printed and the status is 0, unless ``--force`` is
    given (``noxgreen``, pitboss#345).

    Args:
        args: the parsed arguments.
    """
    stop_when_short_of_disk(args)
    runner = functools.partial(run_command, args)
    place = noxgreen.place_of(runner)
    before = noxgreen.green_at(place) if place and not args.force else ""
    if before:
        print(noxgreen.note_of(before))
        return
    lines, modules, sessions = planned(args, runner)
    for each in lines:
        print(each)
    show(noxcheck.run_sessions(runner, time.monotonic, modules, sessions))
    if place:
        noxgreen.record(place, current_time(args).isoformat())
