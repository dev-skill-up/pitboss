"""The commits and addresses a brief names for a PR (keyword: review-brief)."""

from . import brief, pullfacts, reviews, steps

RULED = (steps.Task.FIX_EXECUTION, steps.Task.RULING_STEPS)


def of(base: str, pull: pullfacts.PullFacts | None) -> brief.Heads:
    """What a brief names of a PR.

    Args:
        base: the project's base branch.
        pull: the PR, None for a ticket.

    Returns:
        The heads: the review, and the ruling an Execution fix follows
        (keyword: unfixed-execution, pitboss#390).
    """
    if pull is None:
        return brief.Heads(head="", base=base, approved="", findings="")
    found = pull.review
    step = pull.step
    return brief.Heads(
        head=pull.pull.head.sha,
        base=pull.pull.base,
        approved=found.sha if found else "",
        findings=found.url if found else "",
        ruling=_ruling(step),
        branch=pull.pull.head.branch,
        # the newest review that counts grades the Plan approved, or leaves it as
        # an earlier one graded it (keyword: plan-digest)
        plan_approved=found is not None and found.plan_approved is not False,
        graded=_graded(found),
    )


def _ruling(step: steps.Move) -> str:
    # keyword: unfixed-execution: the ruling an Execution fix follows
    return step.comment if isinstance(step, steps.Next) and step.task in RULED else ""


def _graded(found: reviews.Found | None) -> str:
    # keyword: all-findings: the stage an earlier review graded
    if found is None:
        return ""
    return "plan" if found.plan_alone else "execution"
