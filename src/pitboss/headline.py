"""The ``Head:`` line of a PR body: the head the body describes (keyword: body-head).

``text-lint`` reads the last ``Head: <40 hex>`` line of a body as the head it
describes. The module imports nothing of pitboss, so the flow reads it at no depth.
"""

import re

LINE = re.compile(r"Head: ([0-9a-f]{40})")


def last_head(body: str) -> str:
    """The head the last ``Head:`` line of a body names.

    Args:
        body: the PR body.

    Returns:
        The 40 hex digits; empty when the body has no such line.
    """
    found = [LINE.fullmatch(each.rstrip()) for each in body.splitlines()]
    heads = [each.group(1) for each in found if each]
    return heads[-1] if heads else ""


def is_stale(body: str, head: str) -> bool:
    """Whether a body names a head that is not the PR's.

    Args:
        body: the PR body.
        head: the PR's head SHA.

    Returns:
        True when the body has a ``Head:`` line and its last one is another head.
    """
    return bool(last_head(body)) and last_head(body) != head
