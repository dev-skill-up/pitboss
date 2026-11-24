"""The digest of a Plan and the clean ``plan-check`` of it (plan-check-always)."""

from . import bodydigest, expansion, plandigest, steps


def digest(body: str) -> str:
    """The digest of the Plan section of a body.

    Args:
        body: the PR body.

    Returns:
        The digest.
    """
    return expansion.section_digest(plandigest.section(body))


def clean_text(body: str) -> str:
    """The text of a clean ``plan-check`` of a body's Plan (``plancheck.text``).

    Args:
        body: the PR body the check read.

    Returns:
        The text.
    """
    return "\n".join(
        [
            steps.PLAN_CHECK_FIRST_LINE,
            bodydigest.PLAN_PREFIX + digest(body),
            steps.PLAN_CHECK_OK,
            "",
        ]
    )
