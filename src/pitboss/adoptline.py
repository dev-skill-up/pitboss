"""ADOPT-REVIEW: the review of a PR that ``adopt`` made is of the script.

The keyword is adopt-made.

(pitboss#423.) ``tools/adopt`` of repository-prototype makes one PR for each
repository; its body says so in its first paragraph. The reviewer reads the
script once and approves the rest, so the sweep says the review is not of the
diff.
"""

from typing import Sequence

from . import evidence, pulls
from .markers import Marker


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The ADOPT-REVIEW line of a PR whose body says ``adopt`` made it.

    Args:
        pull: the PR.

    Returns:
        The line, none for any other PR.
    """
    if not evidence.made_by_adopt(pull.pull.body):
        return []
    return [
        f"{Marker.ADOPT_REVIEW.text} {pulls.reference(pull)}: made by `adopt`"
        " (tools/adopt of repository-prototype); the review is of the script"
        " (tools/adopt), not of the diff"
    ]
