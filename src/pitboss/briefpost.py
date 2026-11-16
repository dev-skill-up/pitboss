"""How a review brief says the review is posted (keyword: act-review-form).

``pitboss act review`` writes the repository's form, the grades and the digests of
the body and its Plan, so a reviewer of a Plan and an Execution (or of an Execution
alone) is not told the form, the grade lines or the digests (owner ruling 2026-11-15:
a reviewer does what only a reviewer can do; a tool does the rest).
"""

from typing import Mapping, Sequence

from . import briefgrade
from .briefkind import Kind

EITHER = "<approved or changes needed>"
POST = (
    "Post: post the review with `uvx pitboss act review {reference} kind={kind}"
    "{grades} verdict={either}"
    " findings=<your findings> --config {config} --no-dry-run`; it writes the"
    " repository's form, the grades and the digests it reads from the PR, so"
    " write no other comment."
)
GRADED = {
    Kind.REVIEW_FULL: f" plan={EITHER} execution={EITHER}",
    Kind.REVIEW_PLAN: f" plan={EITHER}",
}


def lines(kind: Kind, values: Mapping[str, str]) -> Sequence[str]:
    """The line that says how a review is posted.

    Args:
        kind: the kind of review brief.
        values: the values the sentences are filled with.

    Returns:
        The line; the grades of the kind are the ones it needs, and the Plan is
        fixed after an approval, so such a review gives the Execution alone.
    """
    grades = GRADED.get(kind, f" execution={EITHER}")
    word = briefgrade.KIND_WORDS[kind]
    return [POST.format(kind=word, grades=grades, either=EITHER, **values)]
