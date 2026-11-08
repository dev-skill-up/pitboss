"""The dry run of a Plan's commands (keyword: plan-check, pitboss#192).

``pitboss plan-check`` runs each row of a Plan but an Impact command in a scratch
worktree of the PR's base (a row that runs nox is refused and not run,
pitboss#251) before the
Plan is approved, so a command that cannot run as written
is a finding of the Plan and not of the Execution hours later. A command that
cannot start, that times out (a wait on a lock or a queue is one) or that was
cut off is not run; any other exit status is shown and is no finding, because
a Plan's command may fail on the base (a test the change makes pass). A row
``pitboss impact PHRASE...`` is searched in this process and its hits must each
have a disposition line in the Plan, at the lines of the PR's head (keyword:
impact-list, pitboss#320). A CI pointer that names a workflow file, job or step
that is not there, and a spec the diff adds that no pointer or group names, are
findings too (keyword: ci-pointer, pitboss#335), and so is a line the diff adds to
a .md or .rst file, except a cut span (keyword: markup-lines, #343, #373). The
module imports no process: the runner, the search and the readers of files are given.
So are a numbered row with no command, read or CI pointer (plan-pointer), a CI run
whose head is not the body's (ci-run), a Done-when that is not the ticket's
(plan-done-when), an interpretation of it (plan-interpretation), an Impact row whose
dispositions are not its hits (impact-count), a diff phrase with no Impact row
(impact-phrase) and a claim that no markup file changed (markup-claim), all
pitboss#317.
"""

import dataclasses
from typing import Callable, Sequence

from . import (
    bodydigest,
    cipointer,
    cipointercheck,
    cirun,
    expansion,
    impact,
    impactcheck,
    impactcount,
    impactphrases,
    markupclaim,
    markuplines,
    noxrow,
    plancheckconfig,
    plandonewhen,
    planpointers,
    steps,
)

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
    # keyword: impact-list (pitboss#320): the search runs here, at the PR's head
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
    """Run the rows of a Plan and say what each did.

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
    """What the Plan's Impact list lacks or cites wrongly at the head.

    Args:
        section: the Plan section of the body.
        search: finds the hits of the phrases of an Impact command.

    Returns:
        The findings (keyword: impact-list, pitboss#320): none when the Plan has
        no Impact command.
    """
    rows = impactcount.phrases(section)
    hits = [hit for each in rows for hit in search(each)]
    # keyword: impact-count (pitboss#317): the hits are cited row by row
    return (
        [*impactcheck.findings(hits, section), *impactcount.findings(section, search)]
        if rows
        else []
    )


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
        The findings: a pointer naming a workflow file, job or step that is not
        there, and a spec the diff adds that no pointer or group names.
    """
    base, head = files
    pointers = cipointer.read(section)
    return [
        *cipointercheck.pointer_findings(pointers, base, head),
        *cipointercheck.spec_findings(added, pointers, settings, head),
    ]


def diff_findings(section: str, patch: str, base: impactphrases.Read) -> Sequence[str]:
    """The phrases of the diff's removed lines that no Impact row searches.

    Args:
        section: the Plan section of the body.
        patch: the PR's diff (``git diff -U0``).
        base: reads a file of the PR's base; None when it is not there.

    Returns:
        A finding for each phrase the diff needs a row for (keyword:
        impact-phrase, pitboss#317).
    """
    wants = impactphrases.wanted(patch, base)
    return impactphrases.uncovered(wants, impactcount.phrases(section))


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
    (impactcount.CHECK, "Impact count findings"),
    (impactphrases.CHECK, "Impact phrase findings"),
    (cipointercheck.CHECK, "CI pointer findings"),
    (cirun.CHECK, "CI run findings"),
    (markuplines.CHECK, "Markup line findings"),
    (markupclaim.CHECK, "Markup claim findings"),
    (planpointers.CHECK, "Plan pointer findings"),
    (plandonewhen.CHECK, "Done-when findings"),
    (plandonewhen.INTERPRETATION, "Interpretation findings"),
)


def verdict(refused: Sequence[int], found: Sequence[str] = ()) -> str:
    """The last line of the report.

    Args:
        refused: the numbers of the rows that did not run.
        found: the findings, a line each: those of the Impact list, the
            ``ci-pointer:`` ones, and the diff's added lines in .md and .rst
            files but a cut span (#373), the ``markup-lines:`` ones.
            The other checks' start with their name (``KINDS``).

    Returns:
        ``Plan check: ok``, or the line that refuses the Plan and names each row
        that did not run, the number of Impact findings, of CI pointer findings
        and of markup line findings.
        The other checks' counts follow.
    """
    if not refused and not found:
        return steps.PLAN_CHECK_OK
    named = ", ".join(str(each) for each in refused)
    counts = _counts(found)
    # a finding of no other check is one of the Impact list (impact-list)
    other = len(found) - sum(count for _, count in counts)
    parts = [
        *([f"rows that did not run: {named}"] if refused else []),
        *([f"Impact findings: {other}"] if other else []),
        *[f"{label}: {count}" for label, count in counts if count],
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
) -> str:
    """The whole output, which is posted as a comment on the PR.

    Args:
        section: the Plan section the rows were run from.
        rows: the report's rows.
        refused: the numbers of the rows that did not run.
        found: the findings of the Impact list, of the CI pointers and of the
            lines the diff adds to .md and .rst files, except a cut span (#373),
            a line each.

    Returns:
        The first line, the rows, the findings, the Plan digest and the verdict.
    """
    digest = f"{bodydigest.PLAN_PREFIX}{bodydigest.of_section(section)}"
    lines = [steps.PLAN_CHECK_FIRST_LINE, *rows, *found, digest]
    return "\n".join([*lines, verdict(refused, found), ""])
