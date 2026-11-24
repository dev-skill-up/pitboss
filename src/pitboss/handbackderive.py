"""Read a PR's hand-back from its body and comments (keyword: standing, #524)."""

from typing import AbstractSet, Sequence

from . import typedstd
from . import handbacks, headlinepattern, plancheckflow, shapes


def derive(
    pull: shapes.Pull,
    comments: Sequence[shapes.Comment],
    trusted: AbstractSet[str],
) -> handbacks.HandedBack:
    """What a PR's body and comments show of its worker's hand-backs.

    Args:
        pull: the PR.
        comments: its issue comments.
        trusted: the author associations whose comments count.

    Returns:
        The head the body's last ``Head:`` line names while the Plan check is clean,
        and the times of the clean checks of trusted authors.
    """
    named = typedstd.findall(headlinepattern.HEAD_LINE, pull.body)
    clean = not plancheckflow.needs_check(pull.body, comments, trusted)
    checked = sorted(
        each.created_at
        for each in comments
        if each.author_association in trusted and plancheckflow.is_clean(each.body)
    )
    return handbacks.HandedBack(
        required=True, head=named[-1] if named and clean else "", checked=checked
    )
