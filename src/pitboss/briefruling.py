"""The lines of the brief of an Opus ruling (keyword: brief, pitboss#118)."""

from typing import Mapping, Sequence

from . import brieftext as text, brieftextorder, rulingwords

OWNER_CONFLICT = (
    "Owner decisions: a Done-when that cannot be met without reversing a decision"
    " of the owner (a closed owner ticket, a rule, a recorded ruling) is"
    " `Ruling: escalate to the owner`, at once, with the artifact (what happened,"
    " the recommendation, the mitigation), and never `reshape`, `split` or"
    " `abandon` around the conflict."
)


def lines(values: Mapping[str, str]) -> Sequence[str]:
    """The lines of a ruling brief.

    Args:
        values: the values the sentences are filled with.

    Returns:
        The lines, one for each rule.
    """
    words = ", ".join(f"`{each.value}`" for each in rulingwords.Ruling)
    return [
        text.RULING_WHO.format_map(values),
        text.RULING_HOW,
        brieftextorder.ORDER_TICKET,
        text.RULING_RECORD.format(words=words),
        OWNER_CONFLICT,
        text.HONEST,
        text.GOAL_ONLY,
        text.RULING_END,
    ]
