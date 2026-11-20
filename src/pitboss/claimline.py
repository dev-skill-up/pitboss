"""STALE-CLAIM: a PR whose body names a head that is not its head.

The keyword is claim-readback.

(quire#1115.) The body named 7ba2eca while the PR head stayed 75f820a: the worker's
claim was never read back. The sweep reads both from the PR and says so, with the
step the PR is at printed after it (the refresh of the body is a step of its own).
"""

from typing import Sequence

from . import headline, pulls, steps, stepwords
from .markers import Marker


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The STALE-CLAIM line of a PR whose body names another head.

    Args:
        pull: the PR.

    Returns:
        The line, none when the body has no ``Head:`` line or names the head.
    """
    body, head = pull.pull.body, pull.pull.head.sha
    if not headline.is_stale(body, head):
        return []
    return [
        f"{Marker.STALE_CLAIM.text} {pulls.reference(pull)}: the body's Head line"
        f" names {headline.last_head(body)}, the PR head is {head} on"
        f" {pull.pull.head.branch}{_step(pull.step)}"
    ]


def _step(step: steps.Move) -> str:
    # keyword: one-path: an idle PR's step is not said
    return f"; step: {stepwords.describe(step)}" if isinstance(step, steps.Next) else ""
