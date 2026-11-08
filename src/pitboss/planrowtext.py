"""The numbered rows of a Plan and their backticked spans (keyword: plan-row).

``planrow`` pairs the rows with the Evidence's commands, and ``planrows``
(keyword: plan-pointer) asks each row for a command, a read or a CI pointer: both
read the rows with this module, which imports only the Plan section and the
prompt of a directive.
"""

import re
from typing import Mapping, Sequence

from . import expansion, plandigest

ROW = re.compile(r"^\s*(?P<number>\d{1,9})[.)]\s+(?P<text>.*)$")
SPAN = re.compile(r"`([^`]+)`")


def rows(body: str) -> Mapping[int, str]:
    """The numbered rows of the Plan section of a body.

    Args:
        body: the PR's body.

    Returns:
        Each row's text by its number (its continuation lines up to the next
        row or a blank line included); the first row of a number is kept.
    """
    found: dict[int, str] = {}
    current = 0
    for line in plandigest.section(body).splitlines()[1:]:
        match = ROW.match(line)
        if match is not None:
            current = int(match.group("number"))
            found.setdefault(current, match.group("text"))
        elif not line.strip():
            current = 0
        elif current and not line.startswith(expansion.PROMPT):
            found[current] += " " + line.strip()
    return found


def spans(text: str) -> Sequence[str]:
    """The backticked spans of a row.

    Args:
        text: the row.

    Returns:
        The text of each pair of backticks, in order.
    """
    return SPAN.findall(text)
