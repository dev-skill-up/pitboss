"""The markup-lines rule at every ``pitboss nox`` and ``pitboss push`` (pitboss#398).

(Keyword: markup-gate.) ``plan-check`` applies the rule of ``markuplines`` only
when a Plan is checked; a merge that restored a line main had deleted reached a
review that way. The gate reads ``git diff origin/main...HEAD`` of the checkout it
runs in and refuses, naming file and line, each line a .md or .rst file gains
that is not a cut of a removed line. It calls git through the runner it is given.
"""

import subprocess
from typing import Sequence

from . import markuplines, running
from .expansion import Outcome
from .noxcheck import Runner

BASE = "origin/main"
DIFF = ["git", "diff", "-U0", "--no-color", "--no-renames", f"{BASE}...HEAD"]


def findings(run: Runner) -> Sequence[str]:
    """What the diff against ``origin/main`` adds to the .md and .rst files.

    Args:
        run: runs a command line.

    Returns:
        A finding for each added line that is not a cut, and for each cut that
        leaves a fragment; none when git cannot give the diff (``nox`` says the
        same of the test selection, and CI's ``plan-check`` judges it).
    """
    done = run(DIFF)
    if done.status:
        return []
    return [*markuplines.added_lines(done.output), *markuplines.fragments(done.output)]


def through(run: running.Run) -> Runner:
    """A runner of command lines through the caller's process runner.

    Args:
        run: runs a command line, raising ``CalledProcessError`` when it fails.

    Returns:
        The runner; a failed command has status 1 and no output.
    """

    def go(command: Sequence[str], /) -> Outcome:
        try:
            return Outcome(status=0, output=run(command).stdout)
        except (subprocess.CalledProcessError, OSError):
            return Outcome(status=1, output="")

    return go
