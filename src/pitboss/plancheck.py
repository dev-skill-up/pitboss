"""The dry run of a Plan's commands (keyword: plan-check, pitboss#192).

``pitboss plan-check`` runs each command of a Plan in a scratch worktree of the
PR's base (a row that runs nox is refused and not run, pitboss#251) before the
Plan is approved, so a command that cannot run as written
is a finding of the Plan and not of the Execution hours later. A command that
cannot start, that times out (a wait on a lock or a queue is one) or that was
cut off is not run; any other exit status is shown and is no finding, because
a Plan's command may fail on the base (a test the change makes pass). A row
``pitboss impact PHRASE...`` is searched in this process and its hits must each
have a disposition line in the Plan, at the lines of this head (keyword:
impact-list, pitboss#320). The module imports no process: the runner and the
search are given.
"""

import dataclasses
from typing import Callable, Sequence

from . import bodydigest, expansion, impact, impactcheck, noxrow, steps

TIMEOUT = 598
COULD_NOT_START = frozenset({126, 127})
Search = Callable[[Sequence[str]], Sequence[impact.Hit]]


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


def _run(each: str, runner: Runner, search: Search) -> Run:
    # keyword: plan-nox (pitboss#251): a nox row is refused and not run
    if noxrow.runs_nox(each):
        return cut_off(noxrow.SENTENCE, 0.0)
    # keyword: impact-list (pitboss#320): the search runs here, at this head
    impact = impactcheck.parse(each)
    if impact is None:
        return runner(each)
    if impact.problem:
        return cut_off(impact.problem, 0.0)
    search(impact.phrases)
    return finished(0, 0.0)


def report(
    section: str, runner: Runner, search: Search
) -> tuple[Sequence[str], Sequence[int]]:
    """Run each command of a Plan and say what each did.

    A row that runs nox is refused and not run (pitboss#251). A row that is an
    Impact command (``pitboss impact``) is run by ``search``, in this process
    (keyword: impact-list, pitboss#320).

    Args:
        section: the Plan section of the body.
        runner: runs one command line.
        search: finds the hits of the phrases of an Impact command.

    Returns:
        The report's lines, a row each, and the numbers of the rows that did
        not run. A directive with no command runs nothing (the commands are
        checked first).
    """
    commands = expansion.commands(section)
    runs = [_run(each, runner, search) for each in commands]
    rows = [line(n, each, run) for n, (each, run) in enumerate(zip(commands, runs), 1)]
    refused = [n for n, run in enumerate(runs, 1) if run.problem]
    return rows, refused


def impact_findings(section: str, search: Search) -> Sequence[str]:
    """What the Plan's Impact list lacks or cites wrongly at this head.

    Args:
        section: the Plan section of the body.
        search: finds the hits of the phrases of an Impact command.

    Returns:
        The findings (keyword: impact-list, pitboss#320): none when the Plan has
        no Impact command.
    """
    parsed = [impactcheck.parse(each) for each in expansion.commands(section)]
    rows = [each for each in parsed if each is not None and not each.problem]
    hits = [hit for each in rows for hit in search(each.phrases)]
    return impactcheck.findings(hits, section) if rows else []


def verdict(refused: Sequence[int], found: Sequence[str] = ()) -> str:
    """The last line of the report.

    Args:
        refused: the numbers of the rows that did not run.
        found: the findings of the Impact list.

    Returns:
        ``Plan check: ok``, or the line that refuses the Plan and names each row
        that did not run and the number of Impact findings.
    """
    if not refused and not found:
        return steps.PLAN_CHECK_OK
    named = ", ".join(str(each) for each in refused)
    parts = [
        *([f"rows that did not run: {named}"] if refused else []),
        *([f"Impact findings: {len(found)}"] if found else []),
    ]
    return f"Plan check: refused, {'; '.join(parts)}"


def text(
    section: str,
    rows: Sequence[str],
    refused: Sequence[int],
    found: Sequence[str] = (),
) -> str:
    """The whole output, which is posted as a comment on the PR.

    Args:
        section: the Plan section the rows were run from.
        rows: the report's rows.
        refused: the numbers of the rows that did not run.
        found: the findings of the Impact list, a line each.

    Returns:
        The first line, the rows, the findings, the Plan digest and the verdict.
    """
    return "\n".join(
        [
            steps.PLAN_CHECK_FIRST_LINE,
            *rows,
            *found,
            f"{bodydigest.PLAN_PREFIX}{bodydigest.of_section(section)}",
            verdict(refused, found),
            "",
        ]
    )
