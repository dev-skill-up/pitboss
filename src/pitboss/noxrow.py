"""The Plan rows that run nox (keyword: plan-nox, pitboss#251).

A Plan names no nox run: CI's ``Run Nox`` step is the proof of the whole suite
(pitboss#179). ``pitboss plan-check`` refuses a Plan command row that runs
``nox``, ``pitboss nox`` or ``uvx ... nox``, and ``lint pr-body`` finds it in the
Plan section; both say the same sentence, which the worker briefs say too.
"""

import re
from typing import Sequence

CHECK = "plan-nox"
SENTENCE = (
    "Nox rows: a Plan row never runs `nox`, `pitboss nox` or `uvx ... nox`; give"
    " the CI pointer instead: the workflow, the run of the head, the job, the step"
    " `Run Nox` and a greppable test name (pitboss#251)."
)
SEGMENTS = re.compile(r"[;&|()\n`]+")
# the words that may stand before nox in a row that runs it
NOX_SEGMENT = re.compile(
    r"\s*(?:(?:timeout|uvx|uv|run|pitboss|python3?|\.|-\S*|\d+|[^\s=]+=\S*)\s+)*"
    r"(?:\S*/)?nox(?:\s|$)"
)


def _segment_runs_nox(segment: str) -> bool:
    return NOX_SEGMENT.match(segment) is not None


def runs_nox(command: str) -> bool:
    """Whether a command line runs nox.

    Args:
        command: the command line of a Plan row.

    Returns:
        True when a part of it (between ``;``, ``&``, ``|`` and the like) is
        nox, or nox behind ``timeout N``, ``pitboss``, ``uvx`` options,
        ``python -m`` and the like.
    """
    return any(_segment_runs_nox(part) for part in SEGMENTS.split(command))


def findings(name: str, planned: Sequence[tuple[int, str]]) -> Sequence[str]:
    """The findings for the Plan rows that run nox.

    Args:
        name: what to call the body in a finding.
        planned: the ``$ `` commands of the Plan section as ``(line, command)``.

    Returns:
        One finding for each command that runs nox.
    """
    return [
        f"{name}: line {line} {command}: {SENTENCE} ({CHECK})"
        for line, command in planned
        if runs_nox(command)
    ]
