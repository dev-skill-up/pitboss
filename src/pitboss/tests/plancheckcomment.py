"""The comment of a clean ``plan-check``, below the tests that read it."""

import dataclasses

from .. import plancheck, plandigest, shapes
from . import blank


def check_comment(body: str, author: str = "MEMBER") -> shapes.Comment:
    """The comment of a clean ``plan-check`` of a body's Plan.

    Args:
        body: the PR body the check read.
        author: its author's association.

    Returns:
        The comment.
    """
    text = plancheck.text(plandigest.section(body), ["row 1: ran"], [])
    return dataclasses.replace(
        blank.COMMENT,
        body=text,
        author_association=author,
        created_at="2026-10-30T00:00:01Z",
        url="https://example.org/check/1",
    )
