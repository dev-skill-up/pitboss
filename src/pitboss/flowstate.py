"""What is recorded of a PR, and what is read from its Opus ruling comments.

The state the review flow reads (``flow``, keyword: review-flow) and the
questions about the newest ruling, and the table of the steps that follow each
ruling. ``flow`` re-exports them under their names.
"""

import dataclasses
import enum
from typing import AbstractSet, Callable, Mapping, Sequence

from . import rulingwords, sessionurl, shapes, steps


class Ci(enum.Enum):
    """The result of the checks on the current head, once finished.

    Attributes:
        GREEN: every check finished and none failed.
        RED: a check failed.
    """

    GREEN = enum.auto()
    RED = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PullState:
    """What is recorded of one PR; every question reads only this.

    Attributes:
        pull: the PR.
        labels: its labels.
        checks: the check runs of its current head.
        graded: every review that counts, in no particular order.
        comments: its issue comments.
        trusted: the author associations whose comments count.
        undraft_clear: whether the runner pressure and the quiet period allow
            an undraft now (read by the caller; the flow does not look).
        merges_only_since: says whether the current head differs from a
            reviewed head by merge commits only (the caller reads the base).
        relock: whether the head branch starts with the relock prefix (the
            caller reads the configuration; keyword: relock).
    """

    pull: shapes.Pull
    labels: AbstractSet[str]
    checks: Sequence[shapes.CheckRun]
    graded: Sequence[shapes.Graded]
    comments: Sequence[shapes.Comment]
    trusted: AbstractSet[str]
    undraft_clear: bool = False
    merges_only_since: Callable[[str], bool] = lambda sha: False
    relock: bool = False


def plan_rejected_last(pr: PullState) -> bool:
    """Whether the newest regular review graded the Plan changes needed.

    With no review of the current head, this is a Plan written after its
    rejection, and it is graded alone, as a draft's is (keyword:
    plan-review-listed, pitboss#167).

    Args:
        pr: the PR.

    Returns:
        True when the newest regular review of any head rejected the Plan.
    """
    regular = (each for each in pr.graded if each.comment)
    newest = max(regular, key=lambda each: each.when, default=None)
    return newest is not None and newest.plan is shapes.Verdict.CHANGES_NEEDED


def is_ruling(body: str) -> bool:
    """Whether a comment is a recorded Opus ruling.

    Args:
        body: the comment.

    Returns:
        True when its first line is exactly ``Opus ruling``.
    """
    lines = sessionurl.lines(body)
    return bool(lines) and lines[0].rstrip() == steps.RULING_FIRST_LINE


def read_ruling(body: str) -> rulingwords.Ruling | None:
    """Read what a ruling comment rules from its second line.

    Args:
        body: the comment (first line ``Opus ruling``, second line
            ``Ruling:`` and one of the words of ``Ruling``).

    Returns:
        The ruling, or None when the comment is none or says no known word.
    """
    lines = sessionurl.lines(body)
    if not is_ruling(body) or len(lines) < 2:
        return None
    return rulingwords.read_line(lines[1])


def newest_ruling(pr: PullState) -> shapes.Comment | None:
    """The newest trusted comment that records an Opus ruling.

    A ruling fixed by an edit keeps its ``created_at``.

    Args:
        pr: the PR.

    Returns:
        The comment, or None when no trusted comment is a ruling.
    """
    found = [
        each
        for each in pr.comments
        if is_ruling(each.body) and each.author_association in pr.trusted
    ]
    return max(found, key=lambda each: each.created_at, default=None)


def readable_comment(
    pr: PullState,
) -> tuple[shapes.Comment, rulingwords.Ruling] | None:
    """The newest Opus ruling comment, with what it rules, when it is readable.

    Args:
        pr: the PR.

    Returns:
        The comment and its ruling, or None when there is none or it has no
        readable ``Ruling:`` line.
    """
    newest = newest_ruling(pr)
    ruled = read_ruling(newest.body) if newest else None
    return None if newest is None or ruled is None else (newest, ruled)


def readable_ruling(pr: PullState) -> rulingwords.Ruling | None:
    """What the newest Opus ruling rules.

    A newer ruling that cannot be read hides an older one that can.

    Args:
        pr: the PR.

    Returns:
        The ruling, or None when there is none or it has no readable
        ``Ruling:`` line.
    """
    answered = readable_comment(pr)
    return answered[1] if answered else None


def has_unreadable_ruling(pr: PullState) -> bool:
    """Whether the newest Opus ruling has no readable ``Ruling:`` line.

    Args:
        pr: the PR.

    Returns:
        True when there is a ruling and it cannot be read.
    """
    return newest_ruling(pr) is not None and readable_ruling(pr) is None


def unreadable_ruling_comment(pr: PullState) -> str:
    """The address of the newest Opus ruling comment.

    Args:
        pr: the PR.

    Returns:
        Its address, empty when there is no ruling or the API gave none.
    """
    newest = newest_ruling(pr)
    return newest.url if newest else ""


# What follows each ruling but ``EXECUTION_IS_APPROVED``, in order. The flow reads
# the first step; the later ones are not wired (a worker's push moves the head and
# the ordinary review gate takes over).
AS_RULED = (
    rulingwords.Ruling.SPLIT,
    rulingwords.Ruling.RESHAPE,
    rulingwords.Ruling.ABANDON,
)
AFTER: Mapping[rulingwords.Ruling, Sequence[steps.Next]] = {
    rulingwords.Ruling.DO_THESE_STEPS: (
        steps.worker(steps.Task.RULING_STEPS),
        steps.regular_review(steps.Stage.RULING_STEPS),
    ),
    rulingwords.Ruling.REVISE_THE_PLAN: (
        steps.worker(steps.Task.REVISE_PLAN),
        steps.regular_review(steps.Stage.PLAN_ONLY),
    ),
    rulingwords.Ruling.ESCALATE: (steps.ruling_escalates(),),
    **dict.fromkeys(AS_RULED, (steps.worker(steps.Task.RULING_AS_GIVEN),)),
}
