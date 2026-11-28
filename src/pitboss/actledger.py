"""The target of ``pitboss act`` and its record in the slot log (keyword: act-verbs).

``act_commands`` runs the verbs; what it reads from its words and what it writes
to the log are here, below it, so the tests reach them without the command.
"""

import dataclasses
from typing import Mapping

from . import actcore, actrun, logline, totaljson
from .textparts import split_at


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Done:
    """A verb that ran.

    Attributes:
        verb: the verb.
        target: its target.
        options: its options.
    """

    verb: str
    target: actcore.Target
    options: Mapping[str, str]


def target_of(word: str) -> actcore.Target:
    """Read a target.

    Args:
        word: ``owner/name#N``, ``owner/name`` or ``all``.

    Returns:
        The target.
    """
    repo, number = split_at(word, "#")
    return actcore.Target(repo=repo, number=int(number) if number.isdigit() else 0)


# the sweep's unledgered check reads these records (keyword: action-matrix)
LEDGERED = {
    "merge": "merge",
    "arm": "arm",
    "undraft": "undraft",
    "label": "label",
    "close": "close",
    "push": "push",
    "dispatch-workflow": "dispatch",
}


def ledger_event(act: actcore.Act, done: Done, now: str) -> logline.Event | None:
    """The slot log's record of a write the sweep checks for.

    Args:
        act: the verbs' world.
        done: the verb that ran.
        now: the time now (ISO 8601).

    Returns:
        The record, or None for a verb the sweep does not check.
    """
    recorded = LEDGERED.get(done.verb)
    if not recorded:
        return None
    target, options = done.target, done.options
    pull = act.hub.pull(target.repo, target.number) if target.number else {}
    head = totaljson.members(pull.get("head"))
    branch = (
        options.get("branch") or options.get("ref") or totaljson.text(head.get("ref"))
    )
    return logline.Event(
        kind=actrun.KIND,
        time=now,
        who=actrun.WHO,
        what=f"{recorded} {target.repo}#{target.number} {branch} at act",
        head=totaljson.text(head.get("sha")),
    )
