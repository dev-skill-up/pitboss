"""PR bodies that name the head their worker handed back (keyword: fake-head, #524)."""

from collections.abc import Mapping

from .. import headnamed

with_head_line = headnamed.with_head_line


def headed(changes: Mapping[str, object], default: str) -> Mapping[str, object]:
    """The changes to a PR's JSON, its body naming the head they give.

    Args:
        changes: the changes.
        default: the head when the changes give none.

    Returns:
        The changes, the body of a PR with a ``Head:`` line.
    """
    head = changes.get("head")
    sha = head["sha"] if isinstance(head, dict) else default
    named = changes.get("body")
    return (
        {**changes, "body": with_head_line(named, str(sha))}
        if isinstance(named, str)
        else changes
    )
