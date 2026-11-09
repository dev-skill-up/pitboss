"""A Done-when that asks for repeated runs (keyword: repeat-runs, pitboss#278).

pitboss rules.md, "No repeat loops" (owner, haiku-rule 142, 2026-10-27): "No
ticket, brief or review asks for N repeated runs". A failing spec is
root-caused from the evidence of one failing run and confirmed by one run, so a
Done-when that asks for a loop, a repeat or N runs is refused where the ticket
is read (``pitboss next TICKET``) and where a brief is linted against it.
"""

import re
from typing import Sequence

from . import donewhen

LABEL = "REPEAT RUNS"
RULE = (
    'pitboss rules.md "No repeat loops" (owner, haiku-rule 142: "No ticket, brief'
    ' or review asks for N repeated runs")'
)
_ASKS = re.compile(
    r"--repeat-each"
    r"|\b(?:loop|loops|looping|repeat|repeats|repeated|repeatedly)\b"
    r"|\b\d+\s+(?:runs?|times|repetitions|iterations)\b"
    r"|\b(?:runs?|times)\s+in\s+a\s+row\b",
    re.IGNORECASE,
)


def asks(text: str) -> Sequence[str]:
    """The words of a Done-when that ask for repeated runs.

    Args:
        text: the Done-when.

    Returns:
        Each distinct match, lower case, in the order of the text.
    """
    return list(dict.fromkeys(each.group(0).lower() for each in _ASKS.finditer(text)))


def reason(words: Sequence[str]) -> str:
    """The sentence that says why a Done-when is refused.

    Args:
        words: what ``asks`` found; not empty.

    Returns:
        The sentence, citing the rule.
    """
    quoted = ", ".join(f"`{each}`" for each in words)
    return f"the Done-when asks for repeated runs ({quoted}), against {RULE}"


def line(ticket: str, text: str) -> str:
    """The line ``pitboss next TICKET`` prints for such a Done-when.

    Args:
        ticket: the ticket, ``owner/repo#N``.
        text: its Done-when.

    Returns:
        The line, or "" when the Done-when asks for no repeated run.
    """
    words = asks(text)
    return f"{LABEL}: {ticket}: {reason(words)}" if words else ""


def findings(name: str, ticket: str | None) -> Sequence[str]:
    """The finding for a brief linted against a ticket that asks for a loop.

    Args:
        name: the brief's name.
        ticket: the ticket's text, or None when it is not given.

    Returns:
        One finding, or none.
    """
    words = [] if ticket is None else asks(donewhen.section(ticket))
    return [f"{name}: {reason(words)} (repeat-runs)"] if words else []
