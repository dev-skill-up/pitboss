"""The sweep's SUPERSEDED POINTER line (keyword: superseded-pointer, pitboss#317).

When an Opus ruling replaces something an approved Plan names, the Plan is not
edited and the Execution says so in one line that names the old test and the new.
The sweep does not stop offering the PR for it: it prints this line, and the
review goes on. ``testnames`` does the same for the lint of the body. A pointer
name that is gone with no such Execution line is a ``test-name`` finding as before.
"""

from typing import Sequence

from . import planrowtext, pulls, testnames

TEXT = "SUPERSEDED POINTER"


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The lines for the Plan rows that name a test the diff removed.

    Args:
        pull: the PR.

    Returns:
        A line for each such row and test whose removal an Execution line
        explains with the new name; none for a relock PR.
    """
    if pull.relock or not pull.gone:
        return []
    return [
        f"{TEXT} {pulls.reference(pull)}: row {number} names {old}, the Execution"
        f" says {new}"
        for number, old, new in _renamed(pull)
    ]


def _renamed(pull: pulls.PullFacts) -> Sequence[tuple[int, str, str]]:
    said = testnames.superseding(pulls.body_of(pull))
    rows = planrowtext.rows(pulls.body_of(pull))
    return [
        (number, old, said[old])
        for number, text in rows.items()
        for old in pull.gone
        if old in said and old in text
    ]
