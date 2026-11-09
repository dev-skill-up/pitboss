"""The prose of a PR body's Plan and Execution (keyword: plan-check, pitboss#317).

The sentences ``pitboss plan-check`` holds to the diff (an Interpretation of a
Done-when item, "No .md or .rst file is changed") are the writer's own words: the
text of the ``## Plan`` and ``## Execution`` sections without the fenced blocks,
which hold the output of commands.
"""

import re
from typing import Sequence

SECTIONS = re.compile(r"(?ms)^## (?:Plan|Execution)[ \t]*$.*?(?=^## |\Z)")
FENCE = re.compile(r"(?ms)^(`{3,}|~{3,}).*?^\1[`~]*[ \t]*$")
PARAGRAPH = re.compile(r"\n\s*\n")


def paragraphs(body: str) -> Sequence[str]:
    """The paragraphs of the Plan and the Execution, outside fenced blocks.

    Args:
        body: the PR's body.

    Returns:
        The paragraphs, in order.
    """
    plain = FENCE.sub("", body)
    return [each for part in SECTIONS.findall(plain) for each in PARAGRAPH.split(part)]
