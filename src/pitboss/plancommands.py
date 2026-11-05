"""The commands of a Plan against the commands of the Evidence (keyword: plan-command).

An approved Plan's command is run as written (pitboss#196): the only reasons to
run another are that it is impossible or dangerous, and then the worker stops,
shows the output that proves it, and the Plan is changed and reviewed first. A
repo rule (quire's "e2e runs through gen-pwa test") does not override an
approved Plan's command. ``plan-command`` is the finding for each ``$ `` command
of the Plan section with no command in an Evidence block ``pitboss expand``
produced that is the same string, or the same string with a cut or a pipe after
it.
"""

import re
from typing import Sequence

from . import evidence, expansion, noxrow, plandigest

# the Plan section as plandigest.section reads it
PLAN_HEADING = re.compile(r"^## Plan\s*$")
ANY_HEADING = re.compile(r"^## ")
# a pipe after the command, which is not the `||` of an or-list
PIPED = re.compile(r"^\s*\|(?!\|)")
CHECK = "plan-command"
MESSAGE = (
    "plan command not run as written: line {line} {command}: run it as written;"
    " the only reasons to run another are that it is impossible or dangerous, and"
    " then stop, show the output that proves it, and change the Plan and have it"
    " reviewed first ({check})"
)


def planned(body: str) -> Sequence[tuple[int, str]]:
    """The commands of the Plan section of a body.

    Args:
        body: the PR's body.

    Returns:
        Each ``$ `` command of the Plan section as ``(line, command)``, the line
        counted from 1 in the body; none when the body has no Plan section or
        the section has a directive with no command.
    """
    section = plandigest.section(body)
    try:
        expansion.commands(section)
    except expansion.TemplateError:
        return []
    inside = False
    found: list[tuple[int, str]] = []
    for number, line in enumerate(body.splitlines(), 1):
        if PLAN_HEADING.match(line):
            inside = True
        elif inside and ANY_HEADING.match(line):
            inside = False
        if inside and line.startswith(expansion.PROMPT):
            found.append((number, line[len(expansion.PROMPT) :]))
    return found


def ran(body: str) -> Sequence[str]:
    """The commands of the produced blocks of the Evidence section.

    Args:
        body: the PR's body.

    Returns:
        The first row of each such block, without its ``$ ``.
    """
    return [
        evidence.first_row(each).removeprefix(expansion.PROMPT)
        for each in evidence.blocks(body)
        if evidence.produced(each) and each.in_evidence
    ]


def same(command: str, run: str) -> bool:
    """Whether a command that ran is a Plan command as written.

    Args:
        command: the Plan's command.
        run: the command in an Evidence block.

    Returns:
        True when they are the same string, or ``run`` is ``command`` followed
        by a pipe (a cut is one).
    """
    return run == command or (
        run.startswith(command) and PIPED.match(run[len(command) :]) is not None
    )


def findings(name: str, body: str) -> Sequence[str]:
    """The findings for the Plan commands the Evidence did not run as written.

    Args:
        name: what to call the body in a finding.
        body: the PR's body.

    Returns:
        One finding for each Plan command with no command in the Evidence that
        is the same, or the same with a cut or a pipe after it.
    """
    done = ran(body)
    return [
        f"{name}: " + MESSAGE.format(line=line, command=command, check=CHECK)
        for line, command in planned(body)
        if not any(same(command, each) for each in done)
    ] + list(
        noxrow.findings(name, planned(body))
    )  # keyword: plan-nox
