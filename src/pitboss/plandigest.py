"""The Plan section of a PR body, which a review digests (keyword: plan-digest).

An approved Plan is never reopened (pitboss#172): a review that grades the Plan
records the Plan section it read as a ``Plan digest: <digest>`` line
(``bodydigest.PLAN_PREFIX``, the digest of ``bodydigest.digest``), and the sweep
compares it with the Plan section of the body now. The section is the text from
the ``## Plan`` heading to the next ``## `` heading, without its ``Head:`` lines
(the head moves with every push and is not the Plan). The module imports nothing
of pitboss, so the flow and the command both read it.
"""

import re

_PLAN_HEADING = re.compile(r"^## Plan\s*$")
_ANY_HEADING = re.compile(r"^## ")
_HEAD_LINE = re.compile(r"^Head: ")


def section(body: str) -> str:
    """The Plan section of a PR body.

    Args:
        body: the PR body.

    Returns:
        The lines from the ``## Plan`` heading up to the next ``## `` heading,
        without ``Head:`` lines; empty when the body has no Plan heading.
    """
    kept: list[str] = []
    inside = False
    for line in body.splitlines():
        if _PLAN_HEADING.match(line):
            inside = True
        elif inside and _ANY_HEADING.match(line):
            break
        if inside and not _HEAD_LINE.match(line):
            kept.append(line)
    return "\n".join(kept)
