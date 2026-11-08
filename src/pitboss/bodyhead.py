"""The body of a PR after a merge of the base: its new ``Head:`` line (pitboss#369).

(Keyword: body-head.) ``text-lint`` reads the last ``Head: <40 hex>`` line of a
PR body as the head the body describes, so a merge of main into the branch
needs exactly one change to the body: a new ``Head:`` line, after the last one.
The module reads no file and calls nothing.
"""

import re

LINE = re.compile(r"Head: ([0-9a-f]{40})")
ENDING = "\r\n"


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


def with_head(body: str, head: str) -> str:
    """The body with a ``Head:`` line for ``head`` after its last ``Head:`` line.

    Nothing else changes: the line ending of that line is the new line's, and a
    body whose last ``Head:`` line already names ``head`` is returned as it is.

    Args:
        body: the PR body, which has a ``Head:`` line.
        head: the new head (40 hex digits).

    Returns:
        The new body.
    """
    lines = body.splitlines(keepends=True)
    at = max(index for index, each in enumerate(lines) if LINE.fullmatch(each.rstrip()))
    if last_head(body) == head:
        return body
    old = lines[at]
    ending = old[len(old.rstrip(ENDING)) :]
    new = f"Head: {head}"
    lines[at] = f"{old}{new}{ending}" if ending else f"{old}\n{new}"
    return "".join(lines)
