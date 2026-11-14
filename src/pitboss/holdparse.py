"""An issue labelled ``pitboss-hold``, parsed once as a hold (keyword: hold).

A hold is an open issue labelled ``pitboss-hold``; its body's ``scope=<word>`` says
what it holds (``all`` when it names none). ``parse`` is the one reading of an issue
as a hold, which the gate and ``act`` both take (plan 6.1: one parse per fact);
``holdissues`` reads the issues.
"""

import re
from typing import Mapping, Sequence

from . import pullrecords
from .totaljson import count, text

HOLD_LABEL = pullrecords.HOLD_LABEL
Held = Mapping[str, Sequence[pullrecords.Hold]]  # each repository's holds


def parse(issue: Mapping[str, object]) -> pullrecords.Hold:
    """An issue labelled ``pitboss-hold``, as a hold.

    Args:
        issue: the issue as GitHub answered.

    Returns:
        Its title (its number when it has none) and its scope.
    """
    scope = re.search(r"scope=(\w+)", text(issue.get("body")))
    title = text(issue.get("title")) or str(count(issue, "number"))
    return pullrecords.Hold(title=title, scope=scope.group(1) if scope else "all")
