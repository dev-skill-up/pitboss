"""Whether a PR's body has a Plan and an Execution (keyword: review-flow)."""

import re

_PLAN_HEADING = re.compile(r"^## Plan\s*$", re.MULTILINE)
_EXECUTION_HEADING = re.compile(r"^## Execution\s*$", re.MULTILINE)


def has_plan_execution_body(body: str) -> bool:
    """Whether a PR body has a Plan section and an Execution section.

    Args:
        body: the PR's body.

    Returns:
        True when both headings (``## Plan``, ``## Execution``) are there.
    """
    return bool(_PLAN_HEADING.search(body) and _EXECUTION_HEADING.search(body))
