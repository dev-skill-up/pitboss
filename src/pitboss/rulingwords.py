"""The words of an Opus ruling (keyword: review-flow).

The ruling is a PR comment whose first line is ``Opus ruling`` and whose second
is ``Ruling:`` and one of the words of ``Ruling``. It is taken as given. The
module imports nothing of pitboss, so ``flow`` and ``rulings`` both read it.
"""

import enum
from typing import Iterable

RULING_LINE_PREFIX = "Ruling: "


class Ruling(enum.Enum):
    """What an Opus ruling rules; the value is the word on its ``Ruling:`` line.

    Attributes:
        DO_THESE_STEPS: a worker does exactly the steps it lists.
        REVISE_THE_PLAN: the plan is revised.
        EXECUTION_IS_APPROVED: the execution is approved.
        SPLIT: the ticket and PR are split.
        RESHAPE: the ticket and PR are reshaped.
        ABANDON: the ticket and PR are abandoned.
        ESCALATE: the owner decides.
    """

    DO_THESE_STEPS = "do these steps"
    REVISE_THE_PLAN = "revise the plan"
    EXECUTION_IS_APPROVED = "execution is approved"
    SPLIT = "split"
    RESHAPE = "reshape"
    ABANDON = "abandon"
    ESCALATE = "escalate to the owner"


_RULINGS = {each.value: each for each in Ruling}
WORDS = ", ".join(_RULINGS)


def read_line(line: str) -> Ruling | None:
    """Read what a ``Ruling:`` line rules.

    Args:
        line: the second line of a ruling comment.

    Returns:
        The ruling, or None when the line is not ``Ruling:`` and a known word.
    """
    second = line.rstrip()
    if not second.startswith(RULING_LINE_PREFIX):
        return None
    return _RULINGS.get(second[len(RULING_LINE_PREFIX) :])


def revised_after(dated: Iterable[tuple[str, Ruling | None]], after: str) -> bool:
    """Whether some ruling says ``revise the plan`` and came after a time.

    A later ruling of another word does not cancel it (keyword:
    plan-digest-rulings, pitboss#475): the Plan is edited as the first ruling
    allowed, and the later one is applied on the Plan as edited.

    Args:
        dated: the time (ISO 8601) and the ruling of each trusted comment, None
            for one that rules nothing readable.
        after: the time of the approving review.

    Returns:
        True when such a ruling was written after that time.
    """
    return any(
        when > after and ruled is Ruling.REVISE_THE_PLAN for when, ruled in dated
    )
