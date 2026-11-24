"""The card of a PR that ended impossible, as a test comment (impossible-state)."""

import dataclasses

from .. import shapes, steps
from . import blank


def impossible(author: str = "MEMBER") -> shapes.Comment:
    """The card a PR that ended impossible carries.

    Args:
        author: the author's association.

    Returns:
        The comment.
    """
    return dataclasses.replace(
        blank.COMMENT,
        body=f"{steps.IMPOSSIBLE_FIRST_LINE}\n\nNothing waits.\n",
        author_association=author,
    )
