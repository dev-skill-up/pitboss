"""The enumeration two at a time: every pair of cells that change different inputs.

For each action, the change each cell makes to the GO world is read back from the
cell (what differs from the GO world), and two changes that touch different inputs
are applied together. The pair must be GO exactly when both cells are GO, and
every stop line of the pair must have a route: no value hides another's stop, and
no pair makes a state with no step. Two changes of the same input are not paired,
since an input holds one value at a time.
"""

import collections
import copy
import dataclasses
import json
import re
from typing import AbstractSet, Mapping, Sequence

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


def _one_action(
    origin: World,
    found: Sequence[tuple[Change, gatewords.Word]],
    verdict: Verdict,
    action: str,
) -> tuple[collections.Counter[str], list[str]]:
    counts: collections.Counter[str] = collections.Counter()
    bad: list[str] = []
    for index, one in enumerate(found):
        for other in found[index + 1 :]:
            kind, wrong = _pair(origin, (one, other), verdict, action)
            counts[kind] += 1
            bad.extend(wrong)
    return counts, bad


def _pair(
    origin: World,
    pair: tuple[tuple[Change, gatewords.Word], tuple[Change, gatewords.Word]],
    verdict: Verdict,
    action: str,
) -> tuple[str, Sequence[str]]:
    # what one pair of changes shows: its count's kind, and the exception if any
    (first, first_word), (second, second_word) = pair
    if set(first) & set(second):
        return "same input", []
    both = apply(origin, first, second)
    answer = verdict(action, both.pull, both.ctx)
    go = first_word == second_word == gatewords.GO
    want = gatewords.GO if go else gatewords.STOP
    lost = routed(answer.stops)
    if answer.word == want and not lost:
        return answer.word.name, []
    said = f"{action} {sorted(first)} {sorted(second)}: {answer.word.name}"
    return "exception", [f"{said}, want {want.name} {lost[:1]}"]


def run(base: World, cells: Sequence[Cell], verdict: Verdict) -> Pairs:
    """Run every pair of cells that change different inputs.

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
