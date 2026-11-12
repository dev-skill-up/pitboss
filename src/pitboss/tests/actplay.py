"""What the tests of the act verbs share (keyword: act-verbs, pitboss#444).

The kit, a verb's refusal, the kinds of the writes made, and the worlds the
tests start from.
"""

from typing import Sequence

from .. import actcore
from . import fakehub, knownkit
from .totalworld import World

GIVEN = knownkit.kit()


def refusal(hub: fakehub.Made, verb: str, **options: str) -> str:
    """Run a verb on the world's PR and say how it was refused.

    Args:
        hub: the hub and the verb's world.
        verb: the verb.
        **options: its options (``_`` for ``-``).

    Returns:
        The refusal's text, or "" when it went.
    """
    return knownkit.refused(lambda: knownkit.act(GIVEN, hub, verb, **options))


def kinds(hub: fakehub.Made) -> Sequence[str]:
    """The kinds of the writes made, in order.

    Args:
        hub: the hub.

    Returns:
        The kinds.
    """
    return [each.kind for each in hub.hub.writes]


def hold_issue(number: int, scope: str) -> actcore.Pull:
    """An open hold issue of one scope.

    Args:
        number: its number.
        scope: what it holds.

    Returns:
        The issue.
    """
    return {
        "number": number,
        "labels": actcore.HOLD_LABEL,
        "state": "open",
        "title": "h",
        "body": f"scope={scope}\nfrom=m",
    }


def stop_line(world: World, prefix: str) -> str:
    """The first stop line of a merge of a world that starts with a prefix.

    Args:
        world: the world.
        prefix: the start of the line.

    Returns:
        The line.
    """
    lines = knownkit.verdict(GIVEN, "merge", world).lines
    return [each for each in lines if each.startswith(prefix)][0]


def red() -> World:
    """The GO world with its check failed.

    Returns:
        The world.
    """
    runs = [
        dict(each, conclusion="failure") if each.get("name") == "check" else each
        for each in knownkit.BASE.ctx["check_runs"]  # type: ignore[attr-defined]
    ]
    return knownkit.change(ctx={"check_runs": runs})
