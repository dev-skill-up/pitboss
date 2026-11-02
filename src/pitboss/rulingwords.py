"""The words of an Opus ruling (keyword: review-flow).

The ruling is a PR comment whose first line is ``Opus ruling`` and whose second
is ``Ruling:`` and one of the words of ``Ruling``. It is taken as given. The
module imports nothing of pitboss, so ``flow`` and ``rulings`` both read it.
"""

import enum

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
