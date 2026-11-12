"""The one form of a declared dependency in a PR body (keyword: blocked-by, quire#1116).

``Blocked-by: owner/name#N`` (or ``#N`` for the PR's own repository) on a line of
its own, one reference to a line. ``ticketblock`` reads it as it reads the older
spellings of a dependency in prose; this check refuses a line that starts like one
and is not the form, so a dependency is never lost to a typo.
"""

import re
from typing import Sequence

FORM = re.compile(r"^Blocked-by: (?:[\w.-]+/[\w.-]+)?#\d+$")
STARTS = re.compile(r"^[\W_]*blocked[\s_-]*(?:by|on)\b", re.IGNORECASE)
NOTE = 'the form is one line "Blocked-by: owner/name#N" for each blocker'


def findings(name: str, body: str) -> Sequence[str]:
    """The lines of a body that start like a dependency and are not the form.

    Args:
        name: what to call the body in a finding.
        body: the PR body.

    Returns:
        One finding for each such line, ending with ``(blocked-by)``.
    """
    return [
        f'{name}: "{row.strip()}" is not a dependency line: {NOTE} (blocked-by)'
        for row in body.splitlines()
        if STARTS.match(row) and not FORM.match(row)
    ]
