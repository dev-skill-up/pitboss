"""A red check of a PR that the base has passed since (keyword: fixed-on-base).

In a repository with a merge queue (``[merge_queue] repositories``) the queue
tests each entry on top of the base, so a PR whose head is red only from checks
that passed on the base after the head's run needs no update of its branch
(pitboss#314): it is enqueued, or reviewed first.
"""

import dataclasses
from typing import Sequence

from . import shapes


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Answer:
    """One failed check of a head and the later run of it that passed on the base.

    Attributes:
        failed: the head's failed check run.
        passed: the base's run of the same check that passed after it.
    """

    failed: shapes.CheckRun
    passed: shapes.CheckRun


def answers(
    failed: Sequence[shapes.CheckRun], base: Sequence[shapes.CheckRun]
) -> Sequence[Answer]:
    """Pair every failed check with the base's later passing run of it.

    Args:
        failed: the failed check runs of the head.
        base: the check runs of the base branch's tip.

    Returns:
        One answer for each failed check, or none unless every failed check
        has one (a head red from a check the base has not passed since is red).
    """
    # the tip's runs: a re-run, or a run that cancelled another, is the later start
    ordered = sorted(base, key=lambda each: (each.started_at, each.id))
    newest = {each.name: each for each in ordered}
    found = [
        Answer(failed=each, passed=newest[each.name])
        for each in failed
        if each.name in newest and _since(each, newest[each.name])
    ]
    return found if failed and len(found) == len(failed) else []


def settle(
    checks: Sequence[shapes.CheckRun], found: Sequence[Answer]
) -> Sequence[shapes.CheckRun]:
    """The checks with each failure the base answered counted as passed.

    The review flow reads these, so a head red only from answered failures gets
    the step a green head gets (pitboss#314).

    Args:
        checks: the head's check runs.
        found: the answers of ``answers``.

    Returns:
        The checks.
    """
    answered = {each.failed.id for each in found}
    return [
        (
            dataclasses.replace(each, failed=False, succeeded=True)
            if each.id in answered
            else each
        )
        for each in checks
    ]


def _since(failed: shapes.CheckRun, passed: shapes.CheckRun) -> bool:
    return (
        passed.succeeded
        and bool(failed.completed_at)
        and passed.completed_at > failed.completed_at
    )
