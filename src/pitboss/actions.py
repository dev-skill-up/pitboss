"""The state-changing actions on GitHub (keyword: action-matrix).

Seen on promise#73: a merge made around a runner-pressure hold, with a raw ``gh``
call no pitboss command saw. Every action that changes a PR on GitHub is one of
``Action``, goes through ``pitboss act``, and writes a ledger record; the sweep
names each GitHub event of these kinds that has no record (``unledgered``). What
allows an action is the decision lookup of ``gateverbs`` (``carriedby`` names the
verb each step carries); there is no state x action table.
"""

import enum
from typing import Mapping, Sequence

VERBS = ("merge", "undraft", "dispatch", "close", "label", "push", "rerun", "delete")
EXEMPT: Mapping[str, str] = {  # an action word of the register that is no Action
    "rerun": "a re-run of a CI job is not an action on a PR; the rule C13 and the"
    " stuck-CI line say when",
    "delete": "a branch is deleted by the owner's own command (bats stale"
    " branches), not by a PR step",
}


class Action(enum.Enum):
    """What changes a PR on GitHub.

    Attributes:
        PUSH: push commits to its branch.
        MERGE: merge it.
        UNDRAFT: mark it ready for review.
        DISPATCH: dispatch a workflow on its branch.
        CLOSE: close it.
        LABEL: put a label on it.
        ARM: arm auto-merge again (keyword: dropped-from-queue).
    """

    PUSH = enum.auto()
    MERGE = enum.auto()
    UNDRAFT = enum.auto()
    DISPATCH = enum.auto()
    CLOSE = enum.auto()
    LABEL = enum.auto()
    ARM = enum.auto()


def word(action: Action) -> str:
    """The word of an action on the command line and in the ledger.

    Args:
        action: the action.

    Returns:
        Its name in lower case.
    """
    return action.name.lower()


def findings(
    wording: Sequence[str], exempt: Mapping[str, str] = EXEMPT
) -> Sequence[str]:
    """What the register's action words get wrong.

    Args:
        wording: the words of the rules of the register.
        exempt: the action words that are no ``Action``, each with its reason.

    Returns:
        A finding for each verb of an action that some rule's words use and that is
        neither an ``Action`` nor exempt.
    """
    known = {word(each) for each in Action} | set(exempt)
    used = {
        verb
        for words in wording
        for verb in VERBS
        if verb in words.lower().replace("-", "")
    }
    return [
        f"the register uses the action word {verb!r}: add it to Action or to EXEMPT"
        for verb in sorted(used - known)
    ]
