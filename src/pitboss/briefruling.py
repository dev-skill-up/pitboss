"""The lines of the brief of an Opus ruling (keyword: brief, pitboss#118)."""

from typing import Mapping

from . import brieftext as text, brieftextorder, rulingwords


def lines(values: Mapping[str, str]) -> list[str]:
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
        text.HONEST,
        text.GOAL_ONLY,
        text.RULING_END,
    ]
