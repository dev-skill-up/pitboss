"""The form of an owner decision card (keyword: how-we-got-here, pitboss#168)."""

from typing import Sequence

from . import analysis

CHECK = "how-we-got-here"

def findings(name: str, body: str) -> Sequence[str]:
    """Check the text of an owner decision card.

    Args:
        name: what to call the text in a finding.
        body: the card's question and reason, as one text.

    Returns:
        The finding ``how-we-got-here`` when the text has no
        ``How we got here`` section with the analysis in it, else none.
    """
    if analysis.has_section(body):
        return []
    return [
        f"{name}: no '{analysis.SECTION}' section: an escalation to the owner"
        " names, for each rejection before it, the finding, the rule or brief"
        " line that should have prevented it, and the prevention filed (a"
        f" pitboss ticket number) ({CHECK})"
    ]
