"""What an action did, read back from the PR (keyword: claim-readback, quire#1115).

``pitboss act`` changes a PR on GitHub and said ``act: ...`` whatever GitHub then
held. After a live action it reads the PR once more and names the fact the
action claims: undrafted, merged, armed, labelled, closed.
"""

import json
from typing import Callable, Mapping, Sequence

from . import actions, actrun, ghapi

NOT_LANDED = "act NOT LANDED"
Read = Mapping[str, object]


def _labelled(words: Sequence[str]) -> Callable[[Read], bool]:
    def has(pull: Read) -> bool:
        found = pull.get("labels")
        names = (
            [each.get("name") for each in found if isinstance(each, dict)]
            if (isinstance(found, list))
            else []
        )
        return bool(words) and words[0] in names

    return has


FIXED: Mapping[actions.Action, tuple[str, Callable[[Read], bool]]] = {
    actions.Action.UNDRAFT: (
        "the PR is no draft",
        lambda pull: pull.get("draft") is False,
    ),
    actions.Action.MERGE: (
        "the PR is merged",
        lambda pull: pull.get("merged") is True,
    ),
    actions.Action.ARM: (
        "auto-merge is armed",
        lambda pull: bool(pull.get("auto_merge")),
    ),
    actions.Action.CLOSE: (
        "the PR is closed",
        lambda pull: pull.get("state") == "closed",
    ),
}


def facts(
    words: Sequence[str],
) -> Mapping[actions.Action, tuple[str, Callable[[Read], bool]]]:
    """The fact each action claims, and how to see it in the PR.

    Args:
        words: the words after the action (the label).

    Returns:
        By action: what it claims and a test of the PR's JSON.
    """
    return {
        **FIXED,
        actions.Action.LABEL: (f"the PR has the label {words[:1]}", _labelled(words)),
    }


def lines(
    github: ghapi.GitHub,
    target: actrun.Target,
    action: actions.Action,
    words: Sequence[str],
) -> Sequence[str]:
    """What the PR holds after an action.

    Args:
        github: the API.
        target: the PR.
        action: the action just made.
        words: the words after it.

    Returns:
        A NOT LANDED line when the PR does not show what the action claims;
        none for a push or a dispatch (read back by their own commands) or when it does.
    """
    wanted = facts(words).get(action)
    if wanted is None:
        return []
    said, holds = wanted
    got = json.loads(ghapi.get(github, f"repos/{target.slug}/pulls/{target.number}"))
    if holds(got):
        return []
    return [
        f"{NOT_LANDED} {actrun.reference(target)}: {actions.word(action)} claims"
        f" {said}, and GitHub says otherwise"
    ]
