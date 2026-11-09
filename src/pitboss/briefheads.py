"""The commits and addresses a brief names for a PR (keyword: review-brief)."""

from . import bodydigest, brief, expansion, plandigest, pulls, steps


def of(base: str, pull: pulls.PullFacts | None) -> brief.Heads:
    """What a brief names of a PR.

    Args:
        base: the project's base branch.
        pull: the PR, None for a ticket.

    Returns:
        The heads: the review or, for a fix round of a refused Plan check, the
        check (keyword: fix-round-kind), and the ruling an Execution fix follows
        (keyword: unfixed-execution, pitboss#390).
    """
    if pull is None:
        return brief.Heads(head="", base=base, approved="", findings="")
    found = pull.review
    step = pull.step
    check = step.comment if step.task is steps.Task.FIX_ROUND else ""
    return brief.Heads(
        head=pull.pull.head.sha,
        base=pull.pull.base,
        approved=found.sha if found else "",
        findings=check or (found.url if found else ""),
        check=bool(check),
        quoted=step.findings,
        ruling=step.comment if step.task is steps.Task.FIX_EXECUTION else "",
        body_digest=bodydigest.digest(pull.pull.body),
        plan_digest=expansion.section_digest(plandigest.section(pull.pull.body)),
    )
