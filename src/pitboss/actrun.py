"""What ``pitboss act`` runs and records for an action (keyword: action-matrix).

The command for each action, and the ledger record that ``unledgered`` later
matches against GitHub's own events.
"""

import datetime
from typing import Mapping, Sequence

from . import actions, logline, steps

WHO = "pitboss act"
KIND = "act"
UNDRAFT_PATH = "repos/{slug}/pulls/{number}"
NEEDS: Mapping[actions.Action, str] = {
    actions.Action.LABEL: "the label's name",
    actions.Action.DISPATCH: "the workflow's file name",
}


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
        return f"{action.value} takes {need} as one word"
    if action is actions.Action.PUSH and not words:
        return "push takes the arguments of git push after the action"
    return ""


def argv(
    action: actions.Action, slug: str, number: int, branch: str, words: Sequence[str]
) -> Sequence[str]:
    """The command that does an action.

    Args:
        action: the action.
        slug: the repository's ``owner/name``.
        number: the PR's number.
        branch: the PR's head branch.
        words: the label, the workflow file, or the arguments of ``git push``.

    Returns:
        The command; every one but the push is a ``gh api`` call.
    """
    issue = f"repos/{slug}/issues/{number}"
    pull = f"repos/{slug}/pulls/{number}"
    return {
        actions.Action.PUSH: lambda: ["git", "push", *words],
        actions.Action.MERGE: lambda: ["gh", "api", "-X", "PUT", f"{pull}/merge"],
        actions.Action.UNDRAFT: lambda: ["gh", "pr", "ready", str(number), "-R", slug],
        actions.Action.DISPATCH: lambda: [
            "gh", "workflow", "run", words[0], "-R", slug, "--ref", branch,
        ],
        actions.Action.CLOSE: lambda: [
            "gh", "api", "-X", "PATCH", "-f", "state=closed", pull,
        ],
        actions.Action.LABEL: lambda: [
            "gh", "api", "-X", "POST", "-f", f"labels[]={words[0]}", f"{issue}/labels",
        ],
    }[action]()


def record(
    action: actions.Action,
    reference: str,
    branch: str,
    step: steps.Next,
    head: str,
    now: datetime.datetime,
) -> logline.Event:
    """The ledger record of an action.

    Args:
        action: the action.
        reference: the PR's ``owner/name#number``.
        branch: the PR's head branch.
        step: the PR's step.
        head: the PR's head commit.
        now: the time now.

    Returns:
        The event: ``what`` is ``<action> <reference> <branch> at <step>``.
    """
    return logline.Event(
        kind=KIND,
        time=now.isoformat(),
        who=WHO,
        what=f"{action.value} {reference} {branch} at {step.step.name}",
        head=head,
    )
