"""The review step as a test expects it, with no standing to build it from."""

from .. import steps

HAND_BACK = steps.worker(steps.Task.HAND_BACK)


def review(stage: steps.Stage) -> steps.Next:
    """The step of a review of a stage.

    Args:
        stage: what the review grades.

    Returns:
        The step ``steps.regular_review`` gives for a standing of that stage.
    """
    return steps.Next(step=steps.Step.REGULAR_REVIEW, stage=stage)
