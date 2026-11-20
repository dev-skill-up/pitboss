"""A clean ``plan-check`` comment for the tests (keyword: plan-check-always)."""

import dataclasses
from .. import bodydigest, expansion, plandigest, shapes, steps
from . import blank


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
            bodydigest.PLAN_PREFIX
            + expansion.section_digest(text=plandigest.section(body)),
            steps.PLAN_CHECK_OK,
            "",
        ]
    )


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
