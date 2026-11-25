"""A clean ``plan-check`` comment for the tests (keyword: plan-check-always)."""

import dataclasses

from .. import shapes, witnessplan
from . import blank

clean_text = witnessplan.clean_text


def clean_check(body: str) -> shapes.Comment:
    """The comment of a clean ``plan-check`` of a body's Plan.

    Args:
        body: the PR body the check read.

    Returns:
        The comment, written before every review and ruling of these tests.
    """
    return dataclasses.replace(
        blank.COMMENT,
        body=clean_text(body),
        author_association="MEMBER",
        created_at="2026-10-29T00:00:00Z",
        url="https://example.org/check/0",
    )
