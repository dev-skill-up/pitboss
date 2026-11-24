"""The standing a review step is built from (keyword: standing, pitboss#507).

A review is offered only for a head and a body that a worker handed back, and that
no review of the same stage already names. ``steps.Standing`` is the value that
says so, ``of`` makes it, and ``steps.regular_review`` takes one, so a review step
cannot be built without it: a PR whose head no worker handed back, or whose state a
review already graded, has no review step, whatever its comments say (quire#1122,
#1125: reviews of a head no worker had handed back).
"""

from typing import AbstractSet, Protocol, Sequence

from . import bodydigest, expansion, handbacks, sessionurl, shapes, steps, typedstd


class Held(Protocol):
    """What the standing of a PR is read from (``flowstate.PullState``)."""

    @property
    def pull(self) -> shapes.Pull:
        """The PR.

        Returns:
            The value.
        """

    @property
    def graded(self) -> Sequence[shapes.Graded]:
        """Its reviews.

        Returns:
            The value.
        """

    @property
    def comments(self) -> Sequence[shapes.Comment]:
        """Its issue comments.

        Returns:
            The value.
        """

    @property
    def trusted(self) -> AbstractSet[str]:
        """The author associations whose comments count.

        Returns:
            The value.
        """

    @property
    def handed(self) -> handbacks.HandedBack:
        """What its worktree recorded of the hand-backs.

        Returns:
            The value.
        """


def _newest_ruling(
    comments: Sequence[shapes.Comment], trusted: AbstractSet[str]
) -> shapes.Comment | None:
    found = [
        each
        for each in comments
        if sessionurl.first_line_is(each.body, steps.RULING_FIRST_LINE)
        and each.author_association in trusted
    ]
    return typedstd.newest(found, lambda each: each.created_at)


def _alone(stage: steps.Stage) -> bool:
    return stage is steps.Stage.PLAN_ONLY


def _names(review: shapes.Graded, pr: Held, stage: steps.Stage, since: str) -> bool:
    # a review of this head and body (as the review recorded the body) of this stage,
    # posted after the newest ruling: a ruling opens another review of the same state
    digest = bodydigest.digest(pr.pull.body)
    same_state = pr.pull.head.sha.startswith(review.sha) and expansion.current_for(
        expansion.Subject.BODY, review.body, digest
    )
    return (
        review.comment
        and same_state
        and (review.execution is None) is _alone(stage)
        and bool(review.sha)
        and review.when > since
    )


def _naming(pr: Held, stage: steps.Stage) -> Sequence[shapes.Graded]:
    # the reviews of this stage that name this head and body, after the newest ruling
    newest = _newest_ruling(pr.comments, pr.trusted)
    since = newest.created_at if newest else ""
    return [each for each in pr.graded if _names(each, pr, stage, since)]


def of(pr: Held, stage: steps.Stage) -> steps.Standing | None:
    """The standing of a PR's head and body for a review of a stage.

    Args:
        pr: the PR.
        stage: what the review would grade.

    Returns:
        A standing when a worker handed this head and body back under the PR's
        newest ruling (or no worker is required) and no review of the stage,
        posted after the newest ruling, names them; else None.
    """
    granted = steps.Standing(
        head=pr.pull.head.sha, body=bodydigest.digest(pr.pull.body), stage=stage
    )
    if not handbacks.covers(pr.handed, granted.head):
        return None
    return None if _naming(pr, stage) else granted


def _answered(pr: Held, stage: steps.Stage) -> steps.Next | None:
    # pitboss#526: a review already grades this state: approved, it is merged; rejected,
    # the worker fixes what it found; no hand-back changes a review that stands
    if not handbacks.covers(pr.handed, pr.pull.head.sha):
        return None
    grades = [(each.plan, each.execution) for each in _naming(pr, stage)]
    approved = shapes.Verdict.APPROVED
    if (approved, approved) in grades:
        return steps.merge()
    rejects = any(shapes.Verdict.CHANGES_NEEDED in each for each in grades)
    task = steps.Task.REVISE_PLAN if _alone(stage) else steps.Task.FIX_EXECUTION
    return steps.worker(task) if rejects else None


def reviewed(pr: Held, stage: steps.Stage) -> steps.Next:
    """The review of a stage once its head and body were handed back.

    Args:
        pr: the PR.
        stage: what the review grades.

    Returns:
        The review for a standing (keyword: standing); else the worker's task to
        hand the head and body back.
    """
    granted = of(pr, stage)
    if granted is None:
        return _answered(pr, stage) or steps.worker(steps.Task.HAND_BACK)
    return steps.regular_review(granted)
