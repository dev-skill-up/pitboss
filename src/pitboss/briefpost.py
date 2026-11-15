"""How a review brief says the review is posted (keyword: act-review-form).

``pitboss act review`` writes the repository's form, the grades and the digests of
the body and its Plan, so a reviewer of a Plan and an Execution (or of an Execution
alone) is not told the form, the grade lines or the digests (owner ruling 2026-11-15:
a reviewer does what only a reviewer can do; a tool does the rest).
"""

from typing import Mapping, Sequence

from .briefkind import Kind

EITHER = "<approved or changes needed>"
POSTED = frozenset({Kind.REVIEW_FULL, Kind.REVIEW_EXECUTION})
POST = (
    "Post: post the review with `uvx pitboss act review {reference} plan={plan}"
    " execution={either} verdict={either}"
    " findings=<your findings> --config {config} --no-dry-run`; it writes the"
    " repository's form, the grades and the digests, so write no other comment."
)


def lines(kind: Kind, values: Mapping[str, str]) -> Sequence[str]:
    """The line that says how a review is posted.

    Args:
        kind: the kind of review brief.
        values: the values the sentences are filled with.

    Returns:
        The line, for a review that grades an Execution; none for another.
    """
    if kind not in POSTED:
        return []
    plan = (
        "approved" if kind is Kind.REVIEW_EXECUTION else "<approved or changes needed>"
    )
    return [POST.format(plan=plan, either=EITHER, **values)]
