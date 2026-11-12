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
from typing import Callable, Mapping, Sequence

from .. import totalanswer, totalroutes, totalverdict
from .totalcells import Cell, Verdict
from .totalworld import World

ABSENT = "<absent>"
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
    return json.dumps(value, sort_keys=True, default=str)


def start(base: World, action: str) -> World:
    """The GO world an action's cells start from.

    Args:
        base: the GO world.
        action: the action.

    Returns:
        The GO world, a draft for an undraft.
    """
    pull = dict(base.pull, draft=True) if action == "undraft" else dict(base.pull)
    return World(pull=pull, ctx=dict(base.ctx))


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
    made = World(pull=copy.deepcopy(origin.pull), ctx=copy.deepcopy(origin.ctx))
    for each in changes:
        for where, value in each.items():
            _put(made, origin, where, value)
    return made


def _one_action(
    origin: World,
    found: Sequence[tuple[Change, totalanswer.Word]],
    verdict: Verdict,
    action: str,
) -> tuple[collections.Counter[str], list[str]]:
    counts: collections.Counter[str] = collections.Counter()
    bad = []
    for index, (first, first_word) in enumerate(found):
        for second, second_word in found[index + 1 :]:
            if set(first) & set(second):
                counts["same input"] += 1
                continue
            both = apply(origin, first, second)
            answer = verdict(action, both.pull, both.ctx)
            want = (
                totalverdict.GO
                if first_word == second_word == totalverdict.GO
                else totalverdict.STOP
            )
            lost = [each for each in answer.lines if totalroutes.route_of(each) is None]
            if answer.word != want or lost:
                counts["exception"] += 1
                bad.append(
                    f"{action} {sorted(first)} {sorted(second)}: {answer.word.name}, want"
                    f" {want.name} {lost[:1]}"
                )
            else:
                counts[answer.word.name] += 1
    return counts, bad


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
    by_action: dict[str, list[tuple[Change, totalanswer.Word]]] = (
        collections.defaultdict(list)
    )
    for cell in cells:
        origin = start(base, cell.action)
        change = change_of(origin, cell.world)
        if change:
            word = verdict(cell.action, cell.world.pull, cell.world.ctx).word
            by_action[cell.action].append((change, word))
    for action, found in by_action.items():
        more, worse = _one_action(start(base, action), found, verdict, action)
        counts.update(more)
        bad.extend(worse)
    return Pairs(counts=counts, exceptions=bad[:12])


def routed(
    lines: Sequence[str], table: Callable[[str], object] = totalroutes.route_of
) -> Sequence[str]:
    """The lines with no route, or that say pitboss does not know.

    Args:
        lines: stop lines.
        table: the routing (the shipped one when none).

    Returns:
        Each line that has no route or is forbidden.
    """
    return [
        each
        for each in lines
        if table(each) is None or totalroutes.FORBIDDEN.search(each)
    ]
