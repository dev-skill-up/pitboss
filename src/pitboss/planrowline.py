"""The sweep's PLAN ROW line (keywords: plan-row, pitboss#259; plan-pointer, #317)."""

from typing import Sequence

from . import plancommands, planrow, pulls, sessionurl
from .markers import Marker


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The line of a PR whose numbered Plan row lacks its Evidence command.

    Args:
        pull: the PR.

    Returns:
        One line naming the first finding of ``planrow.findings`` or of the
        ``plan-pointer`` check (a numbered row with no command, read or CI
        pointer) on the body, before any review round is requested; none when
        there is no finding.
    """
    if pull.relock:
        return []
    body = sessionurl.strip(pull.pull.body or "")
    approved = pull.signals.approved_plans
    found = [
        *planrow.findings("body", body, approved),
        *plancommands.pointer_findings("body", body, approved),
    ]
    if not found:
        return []
    return [
        f"{Marker.PLAN_ROW.text} {pulls.reference(pull)}: {found[0]}; fix the Plan"
        " row (or the Evidence line) before a review round is requested"
    ]
