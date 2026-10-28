"""Bursts: reds that share a cause, so a percentage can be given by cause too."""

import dataclasses
from typing import Mapping, Sequence

from . import redshapes
from .redtime import seconds

BURST_GAP_SECONDS = 6 * 3600


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Burst:
    """Red runs that share a cause.

    Attributes:
        number: its number (1 is the earliest).
        runs: the ids of its runs, earliest first.
        signature: the signature of its earliest run.
    """

    number: int
    runs: Sequence[int]
    signature: str


def _root(parent: dict[int, int], run: int) -> int:
    while parent[run] != run:
        parent[run] = parent[parent[run]]
        run = parent[run]
    return run


def _join(parent: dict[int, int], first: int, second: int) -> None:
    parent[_root(parent, first)] = _root(parent, second)


def _near(before: redshapes.RunFacts, each: redshapes.RunFacts) -> bool:
    gap = seconds(before.run.created_at, each.run.created_at)
    return gap <= BURST_GAP_SECONDS


def group(
    facts: Sequence[redshapes.RunFacts], signatures: Mapping[int, str]
) -> Sequence[Burst]:
    """Group red runs by shared cause.

    Two runs share a cause when they have the same signature (same step and
    error text) and the later started within ``BURST_GAP_SECONDS`` of the
    previous one with it, or when they belong to the same PR.

    Args:
        facts: every red run's facts.
        signatures: each run id's signature.

    Returns:
        The bursts, earliest first.
    """
    ordered = sorted(facts, key=lambda each: each.run.created_at)
    parent = {each.run.id: each.run.id for each in ordered}
    latest: dict[str, redshapes.RunFacts] = {}
    owner: dict[int, int] = {}
    for each in ordered:
        before = latest.get(signatures[each.run.id])
        if before is not None and _near(before, each):
            _join(parent, before.run.id, each.run.id)
        latest[signatures[each.run.id]] = each
        for pull in each.run.pulls:
            _join(parent, owner.setdefault(pull, each.run.id), each.run.id)
    return _bursts(ordered, parent, signatures)


def _bursts(
    ordered: Sequence[redshapes.RunFacts],
    parent: dict[int, int],
    signatures: Mapping[int, str],
) -> Sequence[Burst]:
    members: dict[int, list[int]] = {}
    for each in ordered:
        members.setdefault(_root(parent, each.run.id), []).append(each.run.id)
    return [
        Burst(number=number, runs=runs, signature=signatures[runs[0]])
        for number, runs in enumerate(members.values(), start=1)
    ]
