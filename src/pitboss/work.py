"""The kind of round a PR's step is, and the model a brief goes to.

What a PR needs is the step ``flow.next_step`` gives it (keyword: review-flow): a
worker's round, whose kind is its task (a revision of the plan and nothing else, a
fix of the CI, the Plan and Execution body, the resolution of a conflict, a fix of a
review, or CI quotes), or a review by a new reviewer (a draft's plan-only review
included). The order of work is ``workorder``'s and the decisions ``decide``'s
(keyword: one-path).
"""

from typing import Mapping, Sequence

from . import config, pullfacts, reviews, steps, workitem

Category = workitem.Category
CATEGORY_WORDS = workitem.CATEGORY_WORDS
Item = workitem.Item


REVIEWS = frozenset({Category.REVIEW, Category.RELOCK_REVIEW})
CATEGORY_OF_TASK: Mapping[steps.Task | None, Category] = {
    steps.Task.REVISE_PLAN: Category.REVISE_PLAN,
    steps.Task.FIX_CI: Category.FIX_CI,
    steps.Task.FIRST_ROUND: Category.FIRST_ROUND,
    steps.Task.RESOLVE_CONFLICT: Category.RESOLVE_CONFLICT,
    steps.Task.RULING_STEPS: Category.RULING_STEPS,
    steps.Task.RULING_AS_GIVEN: Category.RULING_AS_GIVEN,
    steps.Task.RUN_PLAN: Category.RUN_PLAN,
    steps.Task.ADD_CI_QUOTES: Category.ADD_CI_QUOTES,
    steps.Task.REFRESH_BODY: Category.REFRESH_BODY,
    steps.Task.SHARED_RED: Category.SHARED_RED,
    steps.Task.FIX_BLOCKED_BY: Category.FIX_BLOCKED_BY,
    steps.Task.AFTER_BLOCKER: Category.AFTER_BLOCKER,
    steps.Task.FINISH_PARTIAL: Category.FINISH_PARTIAL,
}


def category_of(pull: pullfacts.PullFacts) -> Category | None:
    """The kind of round a PR is offered for, from its step alone.

    Args:
        pull: the PR.

    Returns:
        The category, or None when its step is offered for no round.
    """
    step = pull.step
    if isinstance(step, steps.Idle):
        return None
    if step.step is steps.Step.WORKER:
        return CATEGORY_OF_TASK.get(step.task, Category.FIX_REVIEW)
    # review-flow: the step alone decides, so ``next`` and ``slots next`` agree
    if step.step is not steps.Step.REGULAR_REVIEW:
        return None
    alone = step.stage is steps.Stage.PLAN_ONLY  # keyword: plan-review-listed
    fixing = fix_round(pull) and not alone
    if pull.relock:
        return Category.RELOCK_REVIEW  # keyword: relock-last (B9)
    return Category.REVIEW_FIX_ROUND if fixing else Category.REVIEW


def fix_round(pull: pullfacts.PullFacts) -> bool:
    """Whether the newest review asked for changes and the head moved since.

    Only then the review has two different heads to diff (keyword: fix-round,
    pitboss#294): a body edited at one head, or an approval, is no fix round.

    Args:
        pull: the PR.

    Returns:
        True when the newest review says changes needed and names an older head.
    """
    found = pull.review
    asked = found is not None and found.verdict is reviews.Verdict.CHANGES_NEEDED
    return asked and pull.standing is reviews.Standing.OLDER_HEAD


def smallest_model(
    item: Item, slots: config.Slots, failed: Mapping[str, Sequence[str]]
) -> str | None:
    """The smallest model the item may go to.

    Args:
        item: the item.
        slots: the slot configuration.
        failed: each reference's failed models.

    Returns:
        The model, or None when every model has failed it.
    """
    floors = [
        slots.models.index(model)
        for label, model in slots.model_labels.items()
        if label in item.labels and model in slots.models
    ]
    tried = frozenset(failed.get(item.reference, ()))
    for model in slots.models[max(floors, default=0) :]:
        if model not in tried:
            return model
    return None
