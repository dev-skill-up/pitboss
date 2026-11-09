"""A Plan or Execution that says no markup file changed, while the diff changes one.

Seen on pitboss#379 (pitboss#317): the Execution said "No .md or .rst file is
changed" while the diff deleted characters in two. ``pitboss plan-check`` refuses a
sentence of the form "No .md or .rst file is changed" (and "no markup file is
changed") in the Plan or the Execution when ``git diff --name-only`` lists a
``.md`` or ``.rst`` file, and names the file (``markup-claim``). The module reads
no file: the body and the changed paths are given.
"""

import re
from typing import Sequence

from . import bodytext

CHECK = "markup-claim"
SUFFIXES = (".md", ".rst")
KINDS = r"(?:\.md(?:\s+or\s+\.rst)?|\.rst(?:\s+or\s+\.md)?|markup|markdown)"
CLAIM = re.compile(
    rf"\bno\s+{KINDS}\s+files?\s+(?:is|are|was|were|has|have)(?:\s+been)?"
    r"\s+(?:changed|edited|touched|modified)",
    re.IGNORECASE,
)


def findings(body: str, changed: Sequence[str]) -> Sequence[str]:
    """The sentences that deny a change to a markup file the diff makes.

    Args:
        body: the PR's body.
        changed: the paths the PR's diff changes.

    Returns:
        A finding for each such sentence of the Plan or the Execution, naming the
        first ``.md`` or ``.rst`` file the diff changes; none when it changes
        none.
    """
    markup = [each for each in changed if each.endswith(SUFFIXES)]
    if not markup:
        return []
    return [
        f"{CHECK}: the body says `{found.group(0)}`, but the diff changes"
        f" {markup[0]}: say what the change does to it, a cut"
        for paragraph in bodytext.paragraphs(body)
        for found in CLAIM.finditer(paragraph)
    ]
