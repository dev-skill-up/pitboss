"""The sweep's PLAN ROW line (keyword: plan-row, pitboss#259)."""

from typing import Sequence

from . import planrow, pulls, sessionurl
from .markers import Marker


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The line of a PR whose numbered Plan row lacks its Evidence command.

    Args:
        pull: the PR.

    Returns:
        One line naming the first finding of ``planrow.findings`` on the body,
        before any review round is requested; none when there is no finding.
    """
    if pull.relock:
        return []
    found = planrow.findings(
        "body", sessionurl.strip(pull.pull.body or ""), pull.signals.approved_plans
    )
    if not found:
        return []
    return [
        f"{Marker.PLAN_ROW.text} {pulls.reference(pull)}: {found[0]}; fix the Plan"
        " row (or the Evidence line) before a review round is requested"
    ]
