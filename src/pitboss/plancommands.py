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

from . import expansion, noxrow, plandigest, planrow

# the Plan section as plandigest.section reads it
PLAN_HEADING = re.compile(r"^## Plan\s*$")
ANY_HEADING = re.compile(r"^## ")
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


def findings(name: str, body: str, approved: Sequence[str] = ()) -> Sequence[str]:
    """The findings for the Plan commands the Evidence did not run as written.

    Args:
        name: what to call the body in a finding.
        body: the PR's body.
        approved: the digests of the Plans that reviews approved, which the
            Plan-row rule does not judge (keyword: plan-approved, pitboss#296).

    Returns:
        One finding for each Plan command with no command in the Evidence that
        is the same, or the same with a cut or a pipe after it.
    """
    done = planrow.ran(body)
    return [
        f"{name}: " + MESSAGE.format(line=line, command=command, check=CHECK)
        for line, command in planned(body)
        if not any(planrow.same(command, each) for each in done)
    ] + [
        *noxrow.findings(name, planned(body)),  # keyword: plan-nox
        *planrow.findings(name, body, approved),  # keyword: plan-row (pitboss#259)
    ]
