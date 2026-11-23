"""The PR an act verb is about, when it is about one (keyword: accepts).

``act review``, ``push``, ``close``, ``label`` and ``dispatch-workflow`` are carried by
the decision of the PR they change (``gateverbs.allows``); a verb that changes no PR
(a push to a branch with no PR, a label or a close of an issue, a workflow of no PR's
branch) has no decision to carry it.
"""

from typing import Mapping, Sequence

from . import actport, totalanswer
from .totaljson import name_at

Pulls = Sequence[Mapping[str, object]]


def foreign(label: str) -> bool:
    """Whether a label is one another tool puts on a PR (its removal is a step).

    Args:
        label: the label's name.

    Returns:
        True for a label of ``totalanswer.KNOWN_LABELS`` other than ``paused-owner``
        (that one is the owner's; priority and hold labels are settings: T133).
    """
    return label in totalanswer.KNOWN_LABELS - {totalanswer.PAUSED}


def _reference(repo: str, numbers: Sequence[object]) -> str:
    # the first number that is a number, as ``owner/name#number``; empty for none
    first = next((each for each in numbers if isinstance(each, int)), 0)
    return actport.Target(repo=repo, number=first).name if first else ""


def of_branch(pulls: Pulls, repo: str, branch: str) -> str:
    """The open PR whose head is a branch.

    Args:
        pulls: the open PRs of the repository.
        repo: the repository.
        branch: the branch.

    Returns:
        The PR as ``owner/name#number``; empty when no open PR has that head.
    """
    found = [
        each.get("number") for each in pulls if name_at(each, "head", "ref") == branch
    ]
    return _reference(repo, found if branch else [])


def of_number(pulls: Pulls, target: actport.Target) -> str:
    """The target, when it is an open PR (an issue is none).

    Args:
        pulls: the open PRs of the repository.
        target: the PR or issue a verb names.

    Returns:
        The PR as ``owner/name#number``; empty when it is no open PR.
    """
    return _reference(
        target.repo,
        [each.get("number") for each in pulls if each.get("number") == target.number],
    )
