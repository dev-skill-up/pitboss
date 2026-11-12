"""Every claim a worker reports has a read-back (keyword: claim-readback, quire#1115).

The plan and the audit of pitboss#444 asked of each state change whether a gate covers
it, never of each *claim* whether anything reads it back: the worker of quire#1115
reported a push to ``w1113-merge`` and nobody read the PR. ``Claim`` lists what a
worker, a hand-back or a push says happened; ``claims.tsv`` has one row for each, the
GitHub fact it is read back from, the function that reads it and the test that plays
it. ``findings`` is the check: a claim with no row, a row of no claim, a function that
does not exist and a test that does not exist all fail.
"""

import enum
import importlib
from typing import Callable, Sequence
from . import tablefile
from .textparts import hyphenated

FIELDS = 4


class Claim(enum.Enum):
    """What a worker says happened.

    Attributes:
        PUSHED_TO_BRANCH: the commits went to the PR's branch.
        HEAD_IS_SHA: the PR's head is the commit pushed.
        BODY_HEAD_LINE: the body's last Head line names the head.
        CI_GREEN_ON_SHA: the checks of the head passed.
        PLAN_CHECK_POSTED: the Plan check of the head is a comment.
        COMMENT_POSTED: a review or ruling comment is on the PR.
        LABEL_SET: a label is on the PR.
        PR_UNDRAFTED: the PR is ready for review.
        PR_MERGED: the PR is merged.
        BRANCH_RESTARTED_FROM_MAIN: the branch holds the base's tip.
    """

    PUSHED_TO_BRANCH = enum.auto()
    HEAD_IS_SHA = enum.auto()
    BODY_HEAD_LINE = enum.auto()
    CI_GREEN_ON_SHA = enum.auto()
    PLAN_CHECK_POSTED = enum.auto()
    COMMENT_POSTED = enum.auto()
    LABEL_SET = enum.auto()
    PR_UNDRAFTED = enum.auto()
    PR_MERGED = enum.auto()
    BRANCH_RESTARTED_FROM_MAIN = enum.auto()


def name(claim: Claim) -> str:
    """The claim's id in the table.

    Args:
        claim: the claim.

    Returns:
        Its name in lower case with hyphens.
    """
    return hyphenated(claim.name)


def parse(text: str) -> Sequence[Sequence[str]]:
    """The rows of the table.

    Args:
        text: ``claims.tsv``; ``#`` lines and blank lines are skipped.

    Returns:
        The rows; a row with a wrong number of fields is a ``ValueError``.
    """
    return tablefile.rows(text, "claims.tsv", FIELDS)


def reads(where: str) -> bool:
    """Whether ``module.function`` exists in pitboss.

    Args:
        where: the name.

    Returns:
        True when it resolves to a callable.
    """
    return resolves(str(__package__), where)


def resolves(package: str, name: str) -> bool:
    """Whether ``module.attribute`` (one or more attributes) names a callable.

    Args:
        package: the package the module is in.
        name: the name.

    Returns:
        True when it resolves to a callable.
    """
    module, _, rest = name.partition(".")
    try:
        found: object = importlib.import_module(f"{package}.{module}")
        for part in rest.split("."):
            found = getattr(found, part)
    except (ImportError, AttributeError, ValueError):
        return False
    return callable(found)


def findings(table: str, exists: Callable[[str], bool]) -> Sequence[str]:
    """What the table gets wrong.

    Args:
        table: the table.
        exists: whether a named test exists.

    Returns:
        A finding for a claim with no row, a row of no claim, a row with no
        read-back fact, a function that does not exist and a test that does not.
    """
    rows = parse(table)
    named = [each[0] for each in rows]
    found = [
        f"{name(each)} has no read-back row"
        for each in Claim
        if name(each) not in named
    ]
    found += [f"{each} is no claim" for each in named if each not in map(name, Claim)]
    for claim, fact, where, test in rows:
        if not fact.strip():
            found.append(f"{claim}: no GitHub fact to read it back from")
        if not reads(where):
            found.append(f"{claim}: the function {where} does not exist")
        if not exists(test):
            found.append(f"{claim}: the test {test} does not exist")
    return found
