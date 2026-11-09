"""A Plan that adds or loosens a lint needs a test row for what it must still reject.

Six findings of 2026-11-08 were a lint, check or exemption that was new or
loosened and shipped no test of the nearest input it must still reject
(keyword: lint-test, pitboss#358, #180). ``pitboss lint pr-body`` refuses a Plan
whose prose says it adds or loosens one and which has no numbered row that says
a test must still reject (or refuse) the nearest input.
"""

import re
from typing import Mapping, Sequence

from . import cipointer, expansion, plandigest

CHECK = "lint-test"
ADDS = re.compile(
    r"\b(?:(?:new|loosened|relaxed|added)\s+(?:\w+\s+){0,2}?(?:lint|check|exemption)s?"
    r"|(?:adds?|loosens?|relaxes?|widens?)\s+(?:(?:an?|the|new|\w+)\s+){0,3}"
    r"(?:lint|check|exemption)s?)\b",
    re.I,
)
REJECTS = re.compile(
    r"\bnearest input\b|\bmust still (?:reject|refuse)\b"
    r"|\bstill (?:rejects?|refuses?)\b",
    re.I,
)
MESSAGE = (
    "{name}: Plan line {line} adds or loosens a lint, check or exemption, and no"
    " numbered Plan row is a test of the nearest input it must still reject (a row"
    " that names the test and says the input is still rejected or refused); add that"
    " row ({check})"
)


def findings(
    name: str, body: str, rows: Mapping[int, str], approved: Sequence[str] = ()
) -> Sequence[str]:
    """The finding for a Plan that adds or loosens a lint with no refusal-test row.

    Args:
        name: what to call the body in a finding.
        body: the PR's body.
        rows: the numbered rows of its Plan (``planrow.rows``).
        approved: the digests of the Plans that reviews approved, which this
            rule does not judge (keyword: plan-approved, pitboss#296).

    Returns:
        One finding naming the first Plan line that says it adds or loosens a
        lint, check or exemption, when no numbered row of the Plan says a test
        of the nearest input must still reject it; none otherwise.
    """
    plan = plandigest.section(body)
    if set(expansion.accepted_digests(plan)) & set(approved):
        return []
    said = next(
        (n for n, line in cipointer.prose(plan) if ADDS.search(line)),
        None,
    )
    if said is None or any(REJECTS.search(each) for each in rows.values()):
        return []
    return [MESSAGE.format(name=name, line=said, check=CHECK)]
