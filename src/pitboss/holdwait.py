"""A text that tells an agent to wait out a hold names the exception (pitboss#218).

Pitboss is not the final arbiter. A line of ``pitboss sweep``, ``pitboss next``
or ``pitboss push`` that is wrong because of a pitboss bug with a ticket is
overridden on the spot, and the ticket is cited. A brief or a skill text that
tells an agent to hand back under a hold, or not to loop or sleep for a hold,
must say so in the words that follow, or it tells the agent to wait out a hold
that is the tool's own mistake.
"""

import re
from typing import Sequence

EXCEPTION = "known pitboss bug"
WINDOW = 500
SHOWN = 80
_WAITS = re.compile(
    r"\bsleeps? for (?:it|the (?:hold|pressure))\b"
    r"|\bwait(?:s|ed)? (?:out|for) (?:the|a) hold\b"
    r"|\bunder (?:a|the) hold\b",
    re.IGNORECASE,
)


def findings(name: str, body: str) -> Sequence[str]:
    """The places that tell an agent to wait out a hold with no exception.

    Args:
        name: the text's name, for the finding.
        body: the text.

    Returns:
        One finding for each such place: a wait-out instruction with no
        mention of a known pitboss bug in the 500 characters that follow it.
    """
    text = " ".join(body.split())
    return [
        f"{name}: the text tells an agent to wait out a hold, with no exception"
        f" for a hold that comes from a {EXCEPTION} (hold-wait): "
        f"{text[found.start() : found.start() + SHOWN]}"
        for found in _WAITS.finditer(text)
        if EXCEPTION not in text[found.end() : found.end() + WINDOW]
    ]
