"""What ``pitboss act`` runs and records for an action (keyword: action-matrix).

The command for each action, and the ledger record that ``unledgered`` later
matches against GitHub's own events.
"""

import dataclasses
import datetime

from . import actions, logline, steps

WHO = "pitboss act"
KIND = "act"


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
