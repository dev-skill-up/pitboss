"""The step of a rejection that follows a ruling a worker used (keyword: ruling-typed).

Never the owner's (pitboss#517): the owner is reached only by a ruling that says
``escalate to the owner`` or by ``pitboss impossible``. A rejection after a used
ruling is a worker's round.
"""

from . import shapes, steps


def of(review: shapes.Graded, posted: shapes.Comment) -> steps.Next:
    """The step of a rejection after a ruling that was used.

    Args:
        review: the newest review that counts, which rejects.
        posted: the ruling comment.

    Returns:
        The Plan revision when the Plan is rejected, else the fix of the
        Execution against the ruling.
    """
    if review.plan is shapes.Verdict.CHANGES_NEEDED:
        return steps.worker(steps.Task.REVISE_PLAN)
    return steps.worker(steps.Task.FIX_EXECUTION, posted.url)
