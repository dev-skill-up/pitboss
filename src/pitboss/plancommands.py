"""The commands of a Plan against the commands of the Evidence (keyword: plan-command).

An approved Plan's command is run as written (pitboss#196): the only reasons to
run another are that it is impossible or dangerous, and then the worker stops,
shows the output that proves it, and the Plan is changed and reviewed first. A
repo rule (quire's "e2e runs through gen-pwa test") does not override an
approved Plan's command. ``plan-command`` is the finding for each ``$ `` command
of the Plan section with no command in an Evidence block ``pitboss expand``
produced that is the same string, or the same string with a cut or a pipe after
it.
The Plan's numbered rows each have a command, an exact read or a CI pointer
(keyword: plan-pointer, pitboss#317).
"""

import re
from typing import Sequence

from . import expansion, linttests, noxrow, plandigest, planpointers, planrow, planrowtext

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
        is the same, or the same with a cut or a pipe after it, and the findings
        of ``planrow``, ``noxrow`` and ``linttests``.
    """
    done = planrow.ran(body)
    return [
        f"{name}: " + MESSAGE.format(line=line, command=command, check=CHECK)
        for line, command in planned(body)
        if not any(planrow.same(command, each) for each in done)
    ] + [
        *noxrow.findings(name, planned(body)),  # keyword: plan-nox
        *planrow.findings(name, body, approved),  # keyword: plan-row (pitboss#259)
        # keyword: lint-test (pitboss#358)
        *linttests.findings(name, body, planrowtext.rows(body), approved),
        *pointer_findings(name, body, approved),
    ]


def pointer_findings(name: str, body: str, approved: Sequence[str]) -> Sequence[str]:
    """The findings for the numbered Plan rows with no command, read or CI pointer.

    Args:
        name: what to call the body in a finding.
        body: the PR's body.
        approved: the digests of the Plans that reviews approved, which are not
            judged (keyword: plan-approved, pitboss#296).

    Returns:
        One finding for each such row (keyword: plan-pointer, pitboss#317).
    """
    section = plandigest.section(body)
    if set(expansion.accepted_digests(section)) & set(approved):
        return []
    return [
        f"{name}: {each.removeprefix(planpointers.CHECK + ': ')} ({planpointers.CHECK})"
        for each in planpointers.findings(section)
    ]
