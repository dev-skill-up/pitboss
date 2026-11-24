"""A PR body that names the head its worker handed back (keyword: fake-head, #524)."""


def with_head_line(body: str, sha: str) -> str:
    """A PR body that names the head its worker handed back.

    Args:
        body: the body.
        sha: the head.

    Returns:
        The body, with a ``Head:`` line at its end unless it has any.
    """
    named = "\nHead:" in f"\n{body}"
    return body if named else f"{body.rstrip()}\n\nHead: {sha}\n"
