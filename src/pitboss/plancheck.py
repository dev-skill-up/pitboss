"""The dry run of a Plan's commands (keyword: plan-check, pitboss#192).

``pitboss plan-check`` runs each row of a Plan in a scratch worktree of the PR's
base (a row that runs nox is refused and not run, pitboss#251) before the
Plan is approved, so a command that cannot run as written
is a finding of the Plan and not of the Execution hours later. A command that
cannot start, that times out (a wait on a lock or a queue is one) or that was
cut off is not run; any other exit status is shown and is no finding, because
a Plan's command may fail on the base (a test the change makes pass). A CI
pointer that names a workflow file, job or step
that is not there, and a spec the diff adds that no pointer or group names, are
findings too (keyword: ci-pointer, pitboss#335), and so are a row meant as a CI
pointer that is none and a line the Plan cites that the head does not have
(pitboss#358), and a line the diff adds to a .md or .rst file, except a cut span,
and a cut that leaves a fragment (keyword: markup-lines, #343, #373, #358). The
module imports no process: the runner and the readers of files are given.
So are a numbered row with no command, read or CI pointer (plan-pointer), a CI run
whose head is not the body's (ci-run), a Done-when that is not the ticket's, in
its own numbered row (plan-done-when), a measurement of it that the row does not
run (plan-measurement), a ticket whose Done-when was edited after a worker started
(done-when-edited, pitboss#396), an interpretation of it (plan-interpretation) and
a claim that no markup file changed (markup-claim), all pitboss#317 but the
edit. The output sizes of the rows are summed and a Plan whose Evidence will
clearly pass the allowance is warned of (keyword: evidence-size, pitboss#396).
"""

import dataclasses
from typing import Callable, Sequence

from . import (
    bodydigest,
    cipointer,
    cipointercheck,
    cirun,
    expansion,
    markupclaim,
    markuplines,
    noxrow,
    plancheckconfig,
    plandonewhen,
    planpointers,
    plansize,
    steps,
)

TIMEOUT = 598
COULD_NOT_START = frozenset({126, 127})


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Run:
    """What running one command did.

    Attributes:
        status: its exit status (0 when it did not finish).
        seconds: how long it ran.
        problem: why it did not run as written, empty when it ran.
        printed: how many bytes it printed, standard output and error together.
    """

    status: int
    seconds: float
    problem: str = ""
    printed: int = 0


Runner = Callable[[str], Run]


def finished(status: int, seconds: float, printed: int = 0) -> Run:
    """The run of a command that exited.

    Args:
        status: its exit status.
        seconds: how long it ran.
        printed: how many bytes it printed.

    Returns:
        The run, which did not run as written when the shell could not start
        the command (status 126 or 127).
    """
    problem = (
        f"cannot start (exit status {status})" if status in COULD_NOT_START else ""
    )
    return Run(status=status, seconds=seconds, problem=problem, printed=printed)


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


def _run(each: str, runner: Runner) -> Run:
    # keyword: plan-nox (pitboss#251): a nox row is refused and not run
    if noxrow.runs_nox(each):
        return cut_off(noxrow.SENTENCE, 0.0)
    return runner(each)


def report(
    section: str, runner: Runner
) -> tuple[Sequence[str], Sequence[int], Sequence[Run]]:
    """Run the rows of a Plan and say what each did.

    A row that runs nox is refused and not run (pitboss#251).

    Args:
        section: the Plan section of the body.
        runner: runs one command line.

    Returns:
        The report's lines, a row each, the numbers of the rows that did
        not run and what each row did. A directive with no command runs nothing
        (the commands are checked first).
    """
    commands = expansion.commands(section)
    runs = [_run(each, runner) for each in commands]
    rows = [line(n, each, run) for n, (each, run) in enumerate(zip(commands, runs), 1)]
    refused = [n for n, run in enumerate(runs, 1) if run.problem]
    return rows, refused, runs


def size_warnings(section: str, runs: Sequence[Run]) -> Sequence[str]:
    """The warning that the Plan's Evidence will clearly pass the allowance.

    Args:
        section: the Plan section of the body.
        runs: what each of its commands did, in order.

    Returns:
        The warning of ``plansize`` (keyword: evidence-size, pitboss#396), none
        when the commands' output stays within the allowance.
    """
    commands = expansion.commands(section)
    printed = [(each, run.printed) for each, run in zip(commands, runs)]
    return plansize.warnings(printed)


def ci_findings(
    section: str,
    added: Sequence[str],
    settings: plancheckconfig.PlanCheck,
    files: tuple[cipointercheck.Read, cipointercheck.Read],
) -> Sequence[str]:
    """What the Plan's CI pointers get wrong against the tree.

    Args:
        section: the Plan section of the body.
        added: the paths the PR's diff adds.
        settings: the ``[plan_check]`` table (keyword: ci-pointer, pitboss#335).
        files: readers of a file of the PR's base and of its head.

    Returns:
        The findings: a row meant as a pointer that is none (keyword:
        ci-pointer-form, pitboss#358), a pointer naming a workflow file, job or
        step that is not there, a line the Plan cites that the head does not
        have (keyword: cited-line, pitboss#358), and a spec the diff adds that
        no pointer or group names.
    """
    base, head = files
    pointers = cipointer.read(section)
    return [
        *cipointercheck.form_findings(section),
        *cipointercheck.citation_findings(section, head),
        *cipointercheck.pointer_findings(pointers, base, head),
        *cipointercheck.spec_findings(added, pointers, settings, head),
    ]


def form_findings(body: str, section: str, changed: Sequence[str]) -> Sequence[str]:
    """What the body's own words get wrong about its Plan and its diff.

    Args:
        body: the PR's body.
        section: its Plan section.
        changed: the paths the PR's diff changes.

    Returns:
        The findings: a numbered Plan row with no command, read or CI pointer
        (plan-pointer), an Interpretation of a Done-when item
        (plan-interpretation) and a sentence that no markup file is changed
        when one is (markup-claim); pitboss#317.
    """
    return [
        *planpointers.findings(section),
        *plandonewhen.interpretations(body),
        *markupclaim.findings(body, changed),
    ]


KINDS = (
    (cipointercheck.CHECK, "CI pointer findings"),
    (cirun.CHECK, "CI run findings"),
    (markuplines.CHECK, "Markup line findings"),
    (markupclaim.CHECK, "Markup claim findings"),
    (planpointers.CHECK, "Plan pointer findings"),
    (plandonewhen.CHECK, "Done-when findings"),
    (plandonewhen.MEASUREMENT, "Measurement findings"),
    (plandonewhen.EDITED, "Done-when edit findings"),
    (plandonewhen.INTERPRETATION, "Interpretation findings"),
)


def verdict(refused: Sequence[int], found: Sequence[str] = ()) -> str:
    """The last line of the report.

    Args:
        refused: the numbers of the rows that did not run.
        found: the findings, a line each; each starts with the name of its check
            (``KINDS``).

    Returns:
        ``Plan check: ok``, or the line that refuses the Plan and names each row
        that did not run and the number of findings of each check.
    """
    if not refused and not found:
        return steps.PLAN_CHECK_OK
    named = ", ".join(str(each) for each in refused)
    parts = [
        *([f"rows that did not run: {named}"] if refused else []),
        *[f"{label}: {count}" for label, count in _counts(found) if count],
    ]
    return f"Plan check: refused, {'; '.join(parts)}"


def _counts(found: Sequence[str]) -> Sequence[tuple[str, int]]:
    return [
        (label, sum(1 for each in found if each.startswith(f"{check}:")))
        for check, label in KINDS
    ]


def text(
    section: str,
    rows: Sequence[str],
    refused: Sequence[int],
    found: Sequence[str] = (),
    warned: Sequence[str] = (),
) -> str:
    """The whole output, which is posted as a comment on the PR.

    Args:
        section: the Plan section the rows were run from.
        rows: the report's rows.
        refused: the numbers of the rows that did not run.
        found: the findings, a line each.
        warned: the warnings, a line each; they refuse nothing.

    Returns:
        The first line, the rows, the findings, the warnings, the Plan digest
        and the verdict.
    """
    digest = f"{bodydigest.PLAN_PREFIX}{expansion.section_digest(section)}"
    lines = [steps.PLAN_CHECK_FIRST_LINE, *rows, *found, *warned, digest]
    return "\n".join([*lines, verdict(refused, found), ""])
