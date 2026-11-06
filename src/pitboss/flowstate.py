"""What is recorded of a PR, and what is read from its Opus ruling comments.

The state the review flow reads (``flow``, keyword: review-flow) and the
questions about the newest ruling, and the table of the steps that follow each
ruling. ``flow`` re-exports them under their names.
"""

import dataclasses
import enum
from typing import AbstractSet, Callable, Mapping, Sequence

from . import bodydigest, plandigest, rulingwords, sessionurl, shapes, steps


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
        needs_e2e: says whether the diff touches a path the e2e jobs run on and
            no dispatched run of ``check.yml`` at the head has completed (the
            caller reads the files, the configuration and the runs; a draft's
            own run skipped
            the e2e jobs, so it is not one; asked only for a draft whose Plan
            is approved; keyword: run-e2e).
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
    needs_e2e: Callable[[], bool] = lambda: False


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


def plan_edited_without_ruling(pr: PullState) -> bool:
    """Whether the Plan was edited after its approval and no ruling allows it.

    The newest regular review that approves the Plan and records a Plan digest
    is the one compared (keyword: plan-digest, pitboss#172). An Opus ruling
    ``revise the plan`` written after that review authorises the edit.

    Args:
        pr: the PR.

    Returns:
        True when the Plan section of the body is not the one that review read
        and no such ruling was recorded after it.
    """
    newest = newest_plan_digest(pr)
    if newest is None:
        return False
    now = bodydigest.of_section(plandigest.section(pr.pull.body))
    if not bodydigest.changed(newest.plan_digest, now):
        return False
    return not plan_edit_ruled(pr, newest.when)


def approved_digests(graded: Sequence[shapes.Graded]) -> Sequence[str]:
    """The digests of the Plans that regular reviews approved.

    Args:
        graded: every review that counts.

    Returns:
        The ``Plan digest:`` of each regular review that grades the Plan
        approved (keyword: plan-approved, pitboss#296).
    """
    return [each.plan_digest for each in graded if _approves(each)]


def _approves(review: shapes.Graded) -> bool:
    return bool(
        review.comment and review.plan is shapes.Verdict.APPROVED and review.plan_digest
    )


def newest_plan_digest(pr: PullState) -> shapes.Graded | None:
    """The newest regular review that approves the Plan and records its digest.

    Args:
        pr: the PR.

    Returns:
        The review, or None when no review does.
    """
    approving = (each for each in pr.graded if _approves(each))
    return max(approving, key=lambda each: each.when, default=None)


def plan_edit_ruled(pr: PullState, after: str) -> bool:
    """Whether the newest ruling says ``revise the plan`` and came after a time.

    Args:
        pr: the PR.
        after: the time of the approving review (ISO 8601).

    Returns:
        True when the newest readable Opus ruling revises the Plan and was
        written after that time.
    """
    answered = readable_comment(pr)
    return (
        answered is not None
        and answered[1] is rulingwords.Ruling.REVISE_THE_PLAN
        and answered[0].created_at > after
    )


def ruling_hold(pr: PullState) -> steps.Next | None:
    """The step of a PR whose rulings or approved Plan hold it, before any round.

    Args:
        pr: the PR.

    Returns:
        The step to fix an unreadable ruling, or that of a Plan edited with no
        ruling to allow it; None when neither holds.
    """
    if has_unreadable_ruling(pr):
        return steps.fix_ruling(unreadable_ruling_comment(pr))
    return steps.plan_edited() if plan_edited_without_ruling(pr) else None


def unreadable_ruling_comment(pr: PullState) -> str:
    """The address of the newest Opus ruling comment.

    Args:
        pr: the PR.

    Returns:
        Its address, empty when there is no ruling or the API gave none.
    """
    newest = newest_ruling(pr)
    return newest.url if newest else ""


def plan_unrun(pr: PullState, review: shapes.Graded | None) -> steps.Next | None:
    """The worker round of a Plan approved alone after an Opus ruling.

    The ruling's worker round rewrote the Plan and left the Execution unrun,
    and the review after it graded the Plan alone: no one ran the Plan's
    commands (keyword: plan-alone, pitboss#201). The round ends with an edit
    of the body, which the next review does not read (its ``Body:`` digest),
    so the Plan review is not offered again: a draft goes on to its undraft, any
    other PR to the review of its Execution. A draft or not alike.

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        The round, or None when the newest review of the head does not approve
        the Plan alone, or no readable ruling came before it.
    """
    ruled = readable_comment(pr)
    if review is None or ruled is None or review.when <= ruled[0].created_at:
        return None
    alone = review.plan is shapes.Verdict.APPROVED and review.execution is None
    return steps.worker(steps.Task.RUN_PLAN) if alone else None


def ruling_unapplied(pr: PullState) -> rulingwords.Ruling | None:
    """The readable ruling no review and no push has followed.

    A ruling is applied once a regular review or a check run of the head (a
    push) is newer than it; until then its own step is next, whatever the
    newest review that counts says (keyword: ruling-posted, pitboss#294).

    Args:
        pr: the PR.

    Returns:
        The newest readable ruling, or None when none or something followed.
    """
    answered = readable_comment(pr)
    if answered is None:
        return None
    posted, ruled = answered
    reviewed = any(each.when > posted.created_at for each in pr.graded if each.comment)
    pushed = any(each.started_at > posted.created_at for each in pr.checks)
    return None if reviewed or pushed else ruled


def e2e_step(pr: PullState) -> steps.Next | None:
    """The step of a draft whose changed e2e suite has run in no check run.

    A draft's CI skips the e2e jobs, so an approval of it reads no e2e result
    (keyword: run-e2e, pitboss#199). The check workflow is dispatched on its
    branch, and its run is the check run the approval waits for. A draft's own
    completed run does not end the step (it skipped e2e, the case of the
    ticket); only a dispatched run of ``check.yml`` at the head that completed does.

    Args:
        pr: the draft, whose Plan is approved.

    Returns:
        None when its diff touches no path the e2e suite runs on or a
        dispatched run of the head completed; the wait for CI when a check run
        of the head has started and not finished (it is not dispatched again);
        else the dispatch.
    """
    if not pr.needs_e2e():
        return None
    running = [each for each in pr.checks if not each.finished]
    return steps.wait_for_ci() if running else steps.run_e2e(pr.pull.head.branch)


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
