"""The target of ``pitboss act`` and its record in the slot log (keyword: act-verbs).

``act_commands`` runs the verbs; what it reads from its words and what it writes
to the log are here, below it, so the tests reach them without the command.
"""

from typing import Mapping, Sequence

from . import actback, actcore, actions, actrun, ghapi, logline
from .totaljson import mapping, text


def target_of(word: str) -> actcore.Target:
    """Read a target.

    Args:
        word: ``owner/name#N``, ``owner/name`` or ``all``.

    Returns:
        The target.
    """
    repo, _, number = word.partition("#")
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


def ledger_event(
    world: actcore.Act,
    verb: str,
    target: actcore.Target,
    options: Mapping[str, str],
    now: str,
) -> logline.Event | None:
    """The slot log's record of a write the sweep checks for.

    Args:
        world: the verbs' world.
        verb: the verb.
        target: the target.
        options: the options.
        now: the time now (ISO 8601).

    Returns:
        The record, or None for a verb the sweep does not check.
    """
    word = LEDGERED.get(verb)
    if not word:
        return None
    pull = world.hub.pull(target.repo, target.number) if target.number else {}
    head = mapping(pull.get("head"))
    branch = options.get("branch") or options.get("ref") or text(head.get("ref"))
    what = f"{word} {target.repo}#{target.number} {branch} at act"
    return logline.Event(
        kind=actrun.KIND,
        time=now,
        who=actrun.WHO,
        what=what,
        head=text(head.get("sha")),
    )


# the writes whose fact the PR shows, read back after a live verb
READ_BACK = {
    "label": actions.Action.LABEL,
    "undraft": actions.Action.UNDRAFT,
    "merge": actions.Action.MERGE,
    "arm": actions.Action.ARM,
}


def read_back(
    github: ghapi.GitHub,
    verb: str,
    target: actcore.Target,
    options: Mapping[str, str],
) -> Sequence[str]:
    """The ``act NOT LANDED`` line of a live write GitHub does not show.

    Args:
        github: the API.
        verb: the verb.
        target: the PR.
        options: its options (the label's ``name``; ``remove`` claims no label).

    Returns:
        The line, or none when the PR shows the write or the verb claims no fact
        of the PR (keyword: claim-readback).
    """
    action = READ_BACK.get(verb)
    if action is None or options.get("remove"):
        return []
    where = actrun.Target(slug=target.repo, number=target.number, branch="", head="")
    return actback.lines(github, where, action, [options.get("name", "")])
