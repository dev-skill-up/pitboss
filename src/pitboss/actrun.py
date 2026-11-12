"""What ``pitboss act`` runs and records for an action (keyword: action-matrix).

The command for each action, and the ledger record that ``unledgered`` later
matches against GitHub's own events.
"""

import dataclasses
import datetime
from typing import Callable, Mapping, Sequence

from . import actions, logline, steps

WHO = "pitboss act"
KIND = "act"
NEEDS: Mapping[actions.Action, str] = {
    actions.Action.LABEL: "the label's name",
    actions.Action.DISPATCH: "the workflow's file name",
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Target:
    """The PR an action is on.

    Attributes:
        slug: its repository's ``owner/name``.
        number: its number.
        branch: its head branch.
        head: its head commit.
    """

    slug: str
    number: int
    branch: str
    head: str


def reference(target: Target) -> str:
    """The PR as ``owner/name#number``.

    Args:
        target: the PR.

    Returns:
        The reference.
    """
    return "#".join([target.slug, str(target.number)])


def missing(action: actions.Action, words: Sequence[str]) -> str:
    """What the words after the action lack.

    Args:
        action: the action.
        words: the words after it.

    Returns:
        A refusal, empty when the words are what the action takes.
    """
    need = NEEDS.get(action)
    if need and len(words) != 1:
        return f"{actions.word(action)} takes {need} as one word"
    if action is actions.Action.PUSH and not words:
        return "push takes the arguments of git push after the action"
    return ""


API: Mapping[actions.Action, tuple[str, str, Sequence[str]]] = {
    actions.Action.MERGE: ("PUT", "repos/{slug}/pulls/{number}/merge", ()),
    actions.Action.CLOSE: (
        "PATCH",
        "repos/{slug}/pulls/{number}",
        ("-f", "state=closed"),
    ),
    actions.Action.LABEL: (
        "POST",
        "repos/{slug}/issues/{number}/labels",
        ("-f", "labels[]={word}"),
    ),
}


def _undraft(target: Target, words: Sequence[str]) -> Sequence[str]:
    return ["gh", "pr", "ready", str(target.number), "-R", target.slug]


def _dispatch(target: Target, words: Sequence[str]) -> Sequence[str]:
    run = ["gh", "workflow", "run", words[0]]
    return [*run, "-R", target.slug, "--ref", target.branch]


OTHERS: Mapping[actions.Action, Callable[[Target, Sequence[str]], Sequence[str]]] = {
    actions.Action.PUSH: lambda target, words: ["git", "push", *words],
    actions.Action.UNDRAFT: _undraft,
    actions.Action.DISPATCH: _dispatch,
}


def argv(action: actions.Action, target: Target, words: Sequence[str]) -> Sequence[str]:
    """The command that does an action.

    Args:
        action: the action.
        target: the PR.
        words: the label, the workflow file, or the arguments of ``git push``.

    Returns:
        The command; every one but the push is a ``gh`` call.
    """
    if action not in API:
        return OTHERS[action](target, words)
    method, path, fields = API[action]
    given = {"slug": target.slug, "number": target.number, "word": "".join(words[:1])}
    called = [each.format(**given) for each in fields]
    return ["gh", "api", "-X", method, *called, path.format(**given)]


def record(
    action: actions.Action, target: Target, step: steps.Next, now: datetime.datetime
) -> logline.Event:
    """The ledger record of an action.

    Args:
        action: the action.
        target: the PR.
        step: the PR's step.
        now: the time now.

    Returns:
        The event: ``what`` is ``<action> <reference> <branch> at <step>``.
    """
    what = f"{actions.word(action)} {reference(target)} {target.branch}"
    return logline.Event(
        kind=KIND,
        time=now.isoformat(),
        who=WHO,
        what=f"{what} at {step.step.name}",
        head=target.head,
    )
