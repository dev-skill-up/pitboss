"""The ``nox`` command: the local check of a worker (pitboss#210).

Before any session it exits 1, naming file and line, when ``git diff
origin/main...HEAD`` adds a line to a ``.md`` or ``.rst`` file that is not a cut
of a removed line (keyword: markup-gate, ``markupgate``, pitboss#398).
"""

import argparse
import functools
import os
import subprocess
import sys
import time
from typing import Mapping, Sequence

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    alsotests,
    cloneguard,
    configsearch,
    diskwatch,
    expansion,
    markupgate,
    noxcheck,
    noxenv,
    noxgreen,
    selectdiff,
    testselect,
)
from .commandarguments import NOW_ARGUMENT
from .timing import current_time


def run_command(
    args: argparse.Namespace,
    command: Sequence[str],
    environment: Mapping[str, str] | None = None,
) -> expansion.Outcome:
    """Run one command line, standard error joined to standard output.

    Args:
        args: the parsed arguments.
        command: the command line.
        environment: the environment of the child; this process's when none.

    Returns:
        The exit status and what it printed.
    """
    given = {} if environment is None else {"env": environment}
    done = args.safe_run(
        list(command),
        check=False,
        capture_output=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        **given,
    )
    return expansion.Outcome(status=done.returncode, output=done.stdout)


def planned(
    args: argparse.Namespace, runner: noxcheck.Runner
) -> tuple[Sequence[str], Sequence[str], Sequence[noxcheck.Session], Sequence[str]]:
    """Decide which tests the tests session runs.

    Args:
        args: the parsed arguments.
        runner: runs a command line (git, to find the diff).

    Returns:
        The lines to print, the test modules (none: all of them), the sessions
        to run (without the tests session when the diff reaches no test) and the
        changed files whose coverage is judged (none for a run of all the tests,
        whose report is CI's whole one).
    """
    lines, selection = selectdiff.choose(runner)
    extra = args.also or []
    modules = {*selection.chosen, *(each.module for each in extra)}
    reached = selection.everything or modules
    return (
        [*lines, *alsotests.lines_of(extra, selection)],
        [] if selection.everything else sorted(modules),
        tuple(noxcheck.Session) if reached else noxcheck.WITHOUT_TESTS,
        [] if selection.everything else testselect.judged_files(selection),
    )


def show(ran: Sequence[noxcheck.Step]) -> None:
    """Print what the sessions gave, then a line for each session, last.

    The timing lines of the sessions that passed come first (a failed session's
    whole output has its own), then the output of one that failed with the
    command to repeat when it is lint, or on success the line that names the
    proof, and the summary (``noxcheck.summary_of``) as the last lines.

    Args:
        ran: the sessions that ran; a failed one is the last.

    Raises:
        SystemExit: 1 when the last session failed.
    """
    for each in ran:
        if not each.outcome.status:
            for timing in noxcheck.timing_of(each):
                print(timing)
    failed = ran[-1]
    if failed.outcome.status:
        sys.stdout.write(failed.outcome.output)
        for line in noxcheck.rerun_of(failed):
            print(line)
    else:
        print(noxcheck.PROOF)
    for line in noxcheck.summary_of(ran):
        print(line)
    if failed.outcome.status:
        raise SystemExit(1)


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


def stop_before_running(args: argparse.Namespace) -> None:
    """Stop in a clone, when little disk is free or a .md or .rst file gains a line.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 in the main clone with an uncommitted change (keyword:
            clone-guard, pitboss#297), under 5 GiB free, or when a .md or .rst
            file gains a line that is not a cut, naming file and line (keyword:
            markup-gate, pitboss#398).
    """
    cloneguard.refuse_in_clone(args, configsearch.working_directory(args))
    stop_when_short_of_disk(args)
    found = markupgate.findings(functools.partial(run_command, args))
    for each in found:
        print(each)
    if found:
        raise SystemExit(1)


def skipped_as_green(args: argparse.Namespace, place: noxgreen.Place | None) -> bool:
    """Print the NOTE and say so when this head already ran green.

    Args:
        args: the parsed arguments.
        place: the clean head and its record file, none when git cannot say.

    Returns:
        True when the sessions are not to run again.
    """
    before = noxgreen.green_at(place) if place and not args.force else ""
    if before:
        print(noxgreen.note_of(before))
    return bool(before)


def run_planned(
    args: argparse.Namespace, runner: noxcheck.Runner, place: noxgreen.Place | None
) -> None:
    """Print the plan, run the sessions and record a green head.

    Args:
        args: the parsed arguments.
        runner: runs a command line.
        place: the clean head and its record file, none when git cannot say.
    """
    lines, modules, sessions, judged = planned(args, runner)
    for each in lines:
        print(each)
    with noxenv.throwaway_home() as home:
        environment = noxenv.isolated(os.environ, home)
        in_home = functools.partial(run_command, args, environment=environment)
        words = [*noxcheck.covers_of(judged), *modules]
        ran = noxcheck.run_sessions(in_home, time.monotonic, words, sessions)
    show(ran)
    if place:
        noxgreen.record(place, current_time(args).isoformat())


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
        " reach it, how many it left out, what is judged here (the missing lines"
        " and branches of the changed files of src/pitboss, from the tests that"
        " ran, exit 1) and what is left to CI (the rest, in its Run Nox step)."
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
    add_argument(
        "--config",
        default=None,
        help="the project's configuration (a path, or a name in"
        " .claude/pitboss/<name>.toml; default: the search, no fetch), which names"
        " the main clone: in it, with an uncommitted change, the command prints"
        " `refused: this is the main clone; work in your own worktree` and exits 1"
        " (clone-guard, pitboss#297)",
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
    with a throwaway ``HOME`` and no git identity (``noxenv``), and a failing
    session stops the rest and exits 1 with its output, after the command to
    repeat alone when it is lint. The last lines are one for each session, run or
    not (``noxcheck.summary_of``), after the ``test-timing`` lines of a session
    that passed (pitboss#324) and, on success, a line that says CI's ``Run Nox``
    step is the proof of the whole suite. The other sessions are CI's. The tests
    session runs the tests the diff can affect (``testselect``, ``selectdiff``,
    pitboss#331), printed first with the reason, and reports the missing lines
    and branches of the changed files (pitboss#364); a test module added with
    ``--also MODULE=REASON`` runs besides them. A head that already ran green on
    a clean tree is not run again: a ``NOTE`` with the time of that run is
    printed and the status is 0, unless ``--force`` is given (``noxgreen``,
    pitboss#345).

    Args:
        args: the parsed arguments.
    """
    stop_before_running(args)
    runner = functools.partial(run_command, args)
    place = noxgreen.place_of(runner)
    if not skipped_as_green(args, place):
        run_planned(args, runner, place)
