"""The dry run of a Plan's commands (keyword: plan-check, pitboss#192).

``pitboss plan-check`` runs each command of a Plan in a scratch worktree of the
PR's base before the Plan is approved, so a command that cannot run as written
is a finding of the Plan and not of the Execution hours later. A command that
cannot start, that times out (a wait on a lock or a queue is one) or that was
cut off is not run; any other exit status is shown and is no finding, because
a Plan's command may fail on the base (a test the change makes pass). The module
imports no process: the runner is given.
"""

import dataclasses
from typing import Callable, Sequence

from . import bodydigest, expansion, steps

TIMEOUT = 598
COULD_NOT_START = frozenset({126, 127})


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Run:
    """What running one command did.

    Attributes:
        status: its exit status (0 when it did not finish).
        seconds: how long it ran.
        problem: why it did not run as written, empty when it ran.
    """

    status: int
    seconds: float
    problem: str = ""


Runner = Callable[[str], Run]


def finished(status: int, seconds: float) -> Run:
    """The run of a command that exited.

    Args:
        status: its exit status.
        seconds: how long it ran.

    Returns:
        The run, which did not run as written when the shell could not start
        the command (status 126 or 127).
    """
    problem = (
        f"cannot start (exit status {status})" if status in COULD_NOT_START else ""
    )
    return Run(status=status, seconds=seconds, problem=problem)


def cut_off(why: str, seconds: float) -> Run:
    """The run of a command that did not finish or did not start.

    Args:
        why: what happened (``timed out after 598s``).
        seconds: how long it ran.

    Returns:
        The run.
    """
    return Run(status=0, seconds=seconds, problem=why)


def line(number: int, command: str, run: Run) -> str:
    """The line of a row.

    Args:
        number: the row's number, from 1.
        command: the command.
        run: what it did.

    Returns:
        The row, its exit status and duration, or that it did not run and why.
    """
    took = f"{run.seconds:.1f}s"
    if run.problem:
        return f"row {number}: NOT RUN, {run.problem}, {took}: {command}"
    return f"row {number}: ran, exit status {run.status}, {took}: {command}"


def report(section: str, runner: Runner) -> tuple[Sequence[str], Sequence[int]]:
    """Run each command of a Plan and say what each did.

    Args:
        section: the Plan section of the body.
        runner: runs one command line.

    Returns:
        The report's lines, a row each, and the numbers of the rows that did
        not run. A directive with no command runs nothing (the commands are
        checked first).
    """
    commands = expansion.commands(section)
    runs = [runner(each) for each in commands]
    rows = [line(n, each, run) for n, (each, run) in enumerate(zip(commands, runs), 1)]
    refused = [n for n, run in enumerate(runs, 1) if run.problem]
    return rows, refused


def verdict(refused: Sequence[int]) -> str:
    """The last line of the report.

    Args:
        refused: the numbers of the rows that did not run.

    Returns:
        ``Plan check: ok``, or the line that refuses the Plan and names each row.
    """
    if not refused:
        return steps.PLAN_CHECK_OK
    named = ", ".join(str(each) for each in refused)
    return f"Plan check: refused, rows that did not run: {named}"


def text(section: str, rows: Sequence[str], refused: Sequence[int]) -> str:
    """The whole output, which is posted as a comment on the PR.

    Args:
        section: the Plan section the rows were run from.
        rows: the report's rows.
        refused: the numbers of the rows that did not run.

    Returns:
        The first line, the rows, the Plan digest and the verdict.
    """
    return "\n".join(
        [
            steps.PLAN_CHECK_FIRST_LINE,
            *rows,
            f"{bodydigest.PLAN_PREFIX}{bodydigest.of_section(section)}",
            verdict(refused),
            "",
        ]
    )
