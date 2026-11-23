"""The standing a review step is built from (keyword: standing, pitboss#507).

A review is offered only for a head and a body that a worker handed back, and that
no review of the same stage already names. ``steps.Standing`` is the value that
says so, ``of`` makes it, and ``steps.regular_review`` takes one, so a review step
cannot be built without it: a PR whose head no worker handed back, or whose state a
review already graded, has no review step, whatever its comments say (quire#1122,
#1125: reviews of a head no worker had handed back).
"""

from typing import AbstractSet, Protocol, Sequence

from . import bodydigest, expansion, handbacks, sessionurl, shapes, steps


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


def ruling_address(
    comments: Sequence[shapes.Comment], trusted: AbstractSet[str]
) -> str:
    """The address of a PR's newest trusted ruling.

    Args:
        comments: the PR's issue comments.
        trusted: the author associations whose comments count.

    Returns:
        The address, ``handbacks.NO_RULING`` when there is no ruling.
    """
    newest = _newest_ruling(comments, trusted)
    return newest.url if newest and newest.url else handbacks.NO_RULING


def _newest_ruling(
    comments: Sequence[shapes.Comment], trusted: AbstractSet[str]
) -> shapes.Comment | None:
    found = [
        each
        for each in comments
        if sessionurl.first_line_is(each.body, steps.RULING_FIRST_LINE)
        and each.author_association in trusted
    ]
    return max(found, key=lambda each: each.created_at, default=None)


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
    ruling = ruling_address(pr.comments, pr.trusted)
    if not handbacks.covers(pr.handed, granted.head, granted.body, ruling):
        return None
    newest = _newest_ruling(pr.comments, pr.trusted)
    since = newest.created_at if newest else ""
    named = any(_names(each, pr, stage, since) for each in pr.graded)
    return None if named else granted


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
        return steps.worker(steps.Task.HAND_BACK)
    return steps.regular_review(granted)
