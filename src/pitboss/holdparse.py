"""An issue labelled ``pitboss-hold``, parsed once as a hold (keyword: hold).

A hold is an open issue labelled ``pitboss-hold``; its body's ``scope=<word>`` says
what it holds (``all`` when it names none). ``parse`` is the one reading of an issue
as a hold, which the gate and ``act`` both take (plan 6.1: one parse per fact);
``holdissues`` reads the issues.
"""

import re
from typing import AbstractSet, Iterable, Mapping, Sequence

from . import pullrecords
from .totaljson import count, text

HOLD_LABEL = pullrecords.HOLD_LABEL
Held = Mapping[str, Sequence[pullrecords.Hold]]  # each repository's holds
# the verbs each scope holds; ``all`` holds every verb but those that end a hold
HELD: Mapping[str, AbstractSet[str]] = {
    "pushes": frozenset({"push", "update-branch"}),
    "merges": frozenset({"merge", "arm"}),
    "undrafts": frozenset({"undraft"}),
    "ci": frozenset(
        {
            "push",
            "update-branch",
            "merge",
            "arm",
            "undraft",
            "rerun",
            "dispatch-workflow",
            "label",
            "pr-create",
        }
    ),
    "dispatch": frozenset({"dispatch-next"}),
}


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


def covers(hold: pullrecords.Hold, verb: str) -> bool:
    """Whether a hold holds a verb: the one reading of a hold's scope (plan 6.1).

    Args:
        hold: the hold.
        verb: the act verb, or the gate's action (``merge``, ``arm``, ``undraft``).

    Returns:
        True when its scope is ``all`` or holds the verb.
    """
    return hold.scope == "all" or verb in HELD.get(hold.scope, ())


def covering(
    holds: Iterable[pullrecords.Hold], verb: str
) -> Sequence[pullrecords.Hold]:
    """The holds that hold a verb, in order: what the gate and ``act`` both stop on.

    Args:
        holds: the holds, as parsed.
        verb: the act verb, or the gate's action.

    Returns:
        Each that covers it (``covers``).
    """
    return [each for each in holds if covers(each, verb)]
