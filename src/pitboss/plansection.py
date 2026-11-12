"""The Plan section of a PR body (keyword: total-verdict)."""

import re


def plan_section(body: object) -> str | None:
    """The body's Plan section.

    Args:
        body: the PR body.

    Returns:
        The text from ``## Plan`` to the next ``## `` heading; None when the body
        has not exactly one.
    """
    parts = re.split(r"(?m)^## ", body if isinstance(body, str) else "")
    found = [each for each in parts[1:] if re.match(r"Plan\s*\n", each)]
    return found[0] if len(found) == 1 else None
