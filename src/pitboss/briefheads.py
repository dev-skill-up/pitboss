"""The commits and addresses a brief names for a PR (keyword: review-brief)."""

from . import bodydigest, brief, expansion, plandigest, pullfacts, steps

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
        body_digest=bodydigest.digest(pull.pull.body),
        plan_digest=expansion.section_digest(plandigest.section(pull.pull.body)),
    )


def _ruling(step: steps.Move) -> str:
    # keyword: unfixed-execution: the ruling an Execution fix follows
    return step.comment if isinstance(step, steps.Next) and step.task in RULED else ""
