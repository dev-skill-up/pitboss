"""The enumeration's cells together: the verdict is the conjunction of its inputs.

For each action, the change each cell makes to the GO world is read back from the
cell (what differs from the GO world), one change for each input. All the GO
changes together must be GO; each stop change on top of them must be a stop, and
so must all the stop changes together; and every stop line of each world must have
a route, so no value hides another's stop and no world has no step. Each world is
one verdict, so the work grows with the cells and not with their pairs.
"""

import collections
import copy
import dataclasses
import json
import re
from typing import AbstractSet, Callable, Mapping, Sequence

from ..gatestop import Stop
from . import gatewords
from .totalcells import Cell, Verdict
from .totalworld import World, copied

ABSENT = "<absent>"
FORBIDDEN = re.compile(r"no row|not one the verdict|unknown to pitboss")
Change = Mapping[tuple[str, str], object]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Pairs:
    """What running the pairs found.

    Attributes:
        counts: the pairs that were GO, STOP, an exception, or not paired.
        exceptions: the first exceptions, each with what it was.
    """

    counts: Mapping[str, int]
    exceptions: Sequence[str]


def _key(value: object) -> str:
    # a set is written sorted: its str() follows the process's hash seed, and two
    # equal sets built in another order can print in another order
    return json.dumps(value, sort_keys=True, default=_plain)


def _plain(value: AbstractSet[object]) -> Sequence[str]:
    return sorted(map(str, value))


DRAFTED: Mapping[str, Mapping[str, object]] = {"undraft": {"draft": True}}


def start(base: World, action: str) -> World:
    """The GO world an action's cells start from.

    Args:
        base: the GO world.
        action: the action.

    Returns:
        The GO world, a draft for an undraft.
    """
    drafted = DRAFTED.get(action, {})
    return World(pull={**base.pull, **drafted}, ctx=dict(base.ctx))


def change_of(origin: World, world: World) -> Change:
    """What a world changes of another.

    Args:
        origin: the world it starts from.
        world: the world.

    Returns:
        Each input changed and its new value (``ABSENT`` for a field removed).
    """
    found: dict[tuple[str, str], object] = {}
    for name in set(world.pull) | set(origin.pull):
        value = world.pull.get(name, ABSENT)
        if _key(value) != _key(origin.pull.get(name, ABSENT)):
            found[("pull", name)] = value
    for name, value in world.ctx.items():
        if _key(value) != _key(origin.ctx.get(name)):
            found[("ctx", name)] = value
    return found


def _put(made: World, origin: World, where: tuple[str, str], value: object) -> None:
    target = made.pull if where[0] == "pull" else made.ctx
    name = where[1]
    before = origin.ctx.get("timeline")
    if value == ABSENT:
        target.pop(name, None)
    elif (
        where == ("ctx", "timeline")
        and isinstance(value, list)
        and isinstance(before, list)
    ):
        target[name] = [*_events(target[name]), *value[len(before) :]]
    else:
        target[name] = copy.deepcopy(value)


def _events(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def apply(origin: World, *changes: Change) -> World:
    """A world with several changes made.

    Args:
        origin: the world it starts from.
        *changes: the changes.

    Returns:
        The world; added timeline events of each change are all kept.
    """
    made = copied(origin)
    for each in changes:
        for where, value in each.items():
            _put(made, origin, where, value)
    return made


def _checked(
    ask: Callable[[World], gatewords.Answer],
    origin: World,
    made: Sequence[Change],
    want: gatewords.Word,
) -> tuple[str, Sequence[str]]:
    # what one world of several changes shows: its count's kind, and the exception
    answer = ask(apply(origin, *made))
    lost = routed(answer.stops)
    if answer.word == want and not lost:
        return answer.word.name, []
    said = f"{sorted({key for each in made for key in each})}"
    return "exception", [f"{said}: {answer.word.name}, want {want.name} {lost[:1]}"]


def _one_action(
    origin: World,
    found: Sequence[tuple[Change, gatewords.Word]],
    verdict: Verdict,
    action: str,
) -> tuple[collections.Counter[str], list[str]]:
    # the verdict is the conjunction of its inputs: three worlds say so for all of
    # them, with no pair of cells made (the pairs of #444 were 75 thousand verdicts)
    goes: dict[tuple[str, str], Change] = {}
    stops: dict[tuple[str, str], Change] = {}
    every_stop: list[Change] = []
    for change, word in found:
        table = goes if word == gatewords.GO else stops
        table.setdefault(min(change), change)
        if word != gatewords.GO:
            every_stop.append(change)
    counts: collections.Counter[str] = collections.Counter()
    bad: list[str] = []
    worlds = [
        (list(goes.values()), gatewords.GO),
        (list(stops.values()), gatewords.STOP),
        *(([*goes.values(), each], gatewords.STOP) for each in every_stop),
    ]

    def ask(world: World) -> gatewords.Answer:
        return verdict(action, world.pull, world.ctx)

    for made, want in worlds:
        kind, wrong = _checked(ask, origin, made, want)
        counts[kind] += 1
        bad.extend(f"{action} {each}" for each in wrong)
    return counts, bad


def run(base: World, cells: Sequence[Cell], verdict: Verdict) -> Pairs:
    """Run the worlds of the cells' changes together.

    Args:
        base: the GO world.
        cells: the cells.
        verdict: the verdict.

    Returns:
        The counts and the exceptions.
    """
    counts: collections.Counter[str] = collections.Counter()
    bad: list[str] = []
    by_action: dict[str, list[tuple[Change, gatewords.Word]]] = collections.defaultdict(
        list
    )
    for each in cells:
        change = change_of(start(base, each.action), each.world)
        if change:
            word = verdict(each.action, each.world.pull, each.world.ctx).word
            by_action[each.action].append((change, word))
    for action, found in by_action.items():
        more, worse = _one_action(start(base, action), found, verdict, action)
        counts.update(more)
        bad.extend(worse)
    return Pairs(counts=counts, exceptions=bad[:12])


def routed(stops: Sequence[Stop]) -> Sequence[str]:
    """The lines of the stops that say pitboss does not know.

    Args:
        stops: the stops.

    Returns:
        Each such line.
    """
    return [each.line for each in stops if FORBIDDEN.search(each.line)]
