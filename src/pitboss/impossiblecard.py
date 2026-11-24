"""The card of a PR that ended impossible (keyword: impossible-state).

``pitboss impossible`` posts it; the review flow reads it as the PR's terminal
state, which the queue moves past (nothing waits for the owner).
"""

from typing import AbstractSet, Sequence

from . import sessionurl, shapes, steps


def is_card(body: str) -> bool:
    """Whether a comment is the card of an impossible PR.

    Args:
        body: the comment.

    Returns:
        True when its first line is exactly ``Impossible state``.
    """
    return sessionurl.first_line_is(body, steps.IMPOSSIBLE_FIRST_LINE)


def ended(comments: Sequence[shapes.Comment], trusted: AbstractSet[str]) -> bool:
    """Whether a trusted comment says the PR ended impossible.

    Args:
        comments: the PR's comments.
        trusted: the author associations whose comments count.

    Returns:
        True when a comment of a trusted author is the card.
    """
    return any(
        is_card(each.body) and each.author_association in trusted for each in comments
    )
