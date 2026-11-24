"""A PR's hand-back as the flow reads it, made by hand (#524)."""

from .. import handbacks


def held(head: str = "", *checked: str) -> handbacks.HandedBack:
    """What a PR a worker holds shows of its hand-backs.

    Args:
        head: the head its body names under a clean Plan check, "" when none.
        *checked: when each clean Plan check was posted.

    Returns:
        The value.
    """
    return handbacks.HandedBack(required=True, head=head, checked=checked)
