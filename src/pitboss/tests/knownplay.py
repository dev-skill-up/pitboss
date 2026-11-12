"""What the cases of the four tables share beyond the kit: worlds, verbs and rows.

``stopping`` registers the cases whose control is one verdict row that stops a
merge, from rows of data, so each such case is a row and not a function.
"""

import functools
from typing import MutableMapping, Sequence

from .. import dispatchnext
from ..totaljson import JsonMap
from . import fakehub, knownkit
from .totalworld import World


def review_edited(old: str, new: str) -> World:
    """The GO world with its review's text edited.

    Args:
        old: the text replaced.
        new: what replaces it.

    Returns:
        The world.
    """
    return knownkit.change(
        events=[knownkit.review_with(lambda text: text.replace(old, new))]
    )


def stops_in(
    given: knownkit.Kit, *, row: str, world: World, action: str = "merge"
) -> bool:
    """Whether the verdict stops on a row, keyword arguments only.

    Args:
        given: the kit.
        row: the start of the line.
        world: the world.
        action: the action.

    Returns:
        True when it is STOP with a line that starts with the row.
    """
    return knownkit.stops(given, action, world, row)


Stopping = tuple[str, str, str, str, World]


def stopping(
    cases: MutableMapping[str, knownkit.Known], rows: Sequence[Stopping]
) -> None:
    """Register cases whose control is one verdict row that stops a merge.

    Args:
        cases: the module's table, by id.
        rows: each case's id, control, world described, row and world.
    """
    for name, control, what, row, world in rows:
        run = functools.partial(stops_in, row=row, world=world)
        cases[name] = knownkit.Known(control=control, what=what, run=run)


def held(given: knownkit.Kit, hub: fakehub.Made, scope: str) -> None:
    """Hold a scope in the world's repository, for owner message ``m1``.

    Args:
        given: the kit.
        hub: the hub and the verb's world.
        scope: the scope held.
    """
    knownkit.act(given, hub, "hold", number="0", scope=scope, source="m1")


def capped(given: knownkit.Kit, hub: fakehub.Made, message: str, cap: str) -> None:
    """Answer an owner message with a cap.

    Args:
        given: the kit.
        hub: the hub and the verb's world.
        message: the owner message.
        cap: the cap.
    """
    knownkit.act(given, hub, "ack", message=message, kind="cap", cap=cap)


def refuses(given: knownkit.Kit, hub: fakehub.Made, verb: str, **options: str) -> bool:
    """Whether a verb on the world's PR is refused.

    Args:
        given: the kit.
        hub: the hub and the verb's world.
        verb: the verb.
        **options: its options.

    Returns:
        True when it is refused.
    """
    return bool(knownkit.refused(lambda: knownkit.act(given, hub, verb, **options)))


def pull_now(hub: fakehub.Made) -> JsonMap:
    """The world's PR as the hub holds it now.

    Args:
        hub: the hub.

    Returns:
        The PR.
    """
    return hub.act.hub.pull(knownkit.REPO, knownkit.NUMBER)


def dispatch_refused(
    given: knownkit.Kit, hub: fakehub.Made, state: dispatchnext.State
) -> str:
    """Whether ``dispatch-next`` over a state is refused.

    Args:
        given: the kit.
        hub: the hub and the verb's world.
        state: what the order reads.

    Returns:
        The refusal's text, or "" when it answered.
    """
    return knownkit.refused(lambda: knownkit.dispatch(given, hub, state))


def brief_text(given: knownkit.Kit, repo: str, *paths: str) -> str:
    """The kit's brief for a ticket of a real repository, alone.

    Args:
        given: the kit.
        repo: the repository.
        *paths: the ticket's paths.

    Returns:
        The brief.
    """
    return knownkit.brief_for(given, repo, *paths)[0]


def plan_row(row: str) -> str:
    """The GO world's body with a row added to its Plan.

    Args:
        row: the row.

    Returns:
        The body.
    """
    return knownkit.BODY.replace("## Plan\n", f"## Plan\n\n{row}\n", 1)


def edit_refused(given: knownkit.Kit, body: str) -> str:
    """Whether ``pr-edit`` of the world's PR to a body is refused.

    Args:
        given: the kit.
        body: the new body.

    Returns:
        The refusal's text, or "" when it went.
    """
    return knownkit.refused(
        lambda: knownkit.act(given, knownkit.made(given), "pr-edit", body=body)
    )
