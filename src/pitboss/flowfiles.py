"""The modules of the review flow, and a diff that changes one (keyword: flow-change).

The flow is what decides the next step of a PR: ``flow``, ``flowstate``, ``steps``,
the rounds, the ``next`` family, the plans, the reviews, the rulings and the slots.
A change to one of them comes with a change to the register (``rules.tsv``) or to
the scenarios (``tests/scenarios``), so the rule it serves and the timeline that
shows it are written down (pitboss#444, item 12). The module reads nothing: the
diff is given.
"""

import re
from typing import Sequence

FLOW = re.compile(
    r"^src/pitboss/(?:flow|flowstate|steps|rounds|roundline|next\w*"
    r"|plan\w*|review\w*|ruling\w*|slot\w*)\.py$"
)
RECORDED = re.compile(r"^src/pitboss/(?:rules\.tsv|tests/scenarios/.+)$")
FILE = re.compile(r"^diff --git a/(?P<old>\S+) b/(?P<new>\S+)$", re.MULTILINE)
UNRECORDED = (
    "flow-change: `{path}` is a module of the flow and the diff changes neither"
    " `src/pitboss/rules.tsv` nor a file of `tests/scenarios`: add the rule's row or"
    " the timeline that shows the change"
)


def paths_of(diff: str) -> Sequence[str]:
    """The files a diff changes.

    Args:
        diff: the output of ``git diff``.

    Returns:
        The new path of each file, an old path of a rename too.
    """
    return [each for found in FILE.finditer(diff) for each in found.groups()]


def modules_of(paths: Sequence[str]) -> Sequence[str]:
    """The modules of the flow among some paths.

    Args:
        paths: file paths from the root of the repository.

    Returns:
        The paths of the flow, once each, in order.
    """
    return list(dict.fromkeys(each for each in paths if FLOW.match(each)))


def findings(diff: str) -> Sequence[str]:
    """The flow modules a diff changes with no register row or scenario beside.

    Args:
        diff: the output of ``git diff``.

    Returns:
        A finding for each module of the flow the diff changes, when the diff
        changes neither ``rules.tsv`` nor a file under ``tests/scenarios``.
    """
    paths = paths_of(diff)
    if any(RECORDED.match(each) for each in paths):
        return []
    return [UNRECORDED.format(path=each) for each in modules_of(paths)]
