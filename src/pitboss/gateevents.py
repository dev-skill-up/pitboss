"""The stops of the events since the newest review (keyword: gate).

A label pitboss does not apply, and any event that is not benign, make the newest
review one of an older state (pitboss#444, the act verdict's row of the timeline).
It reads the typed timeline ``pullstate`` made (plan 6.1).
"""

import functools
from typing import AbstractSet, Sequence

from . import enumeration
from .gatestop import Route, Stop
from .pullrecords import Event, GateState, listed
from .totalanswer import KNOWN_LABELS

LABEL_EVENTS = frozenset({"labeled", "unlabeled"})


@functools.cache
def stale_events() -> AbstractSet[str]:
    """The documented timeline kinds after which the newest review is stale.

    Returns:
        The kinds of ``enumeration/stale-events.txt``.
    """
    return frozenset(enumeration.shipped("stale-events.txt").split())


def _event_stop(event: Event, benign: AbstractSet[str]) -> Sequence[Stop]:
    # a label pitboss does not apply, or an event after which the review is stale
    kind = event.kind
    if kind in LABEL_EVENTS:
        label = event.label
        if label in KNOWN_LABELS:
            return []
        line = f"event {kind} {label or None}: a label pitboss does not apply"
        return [Stop(route=Route.LABEL, line=line)]
    if kind in benign:
        return []
    line = f"event {kind}: the review is of an older state; review again"
    return [Stop(route=Route.REVIEW, line=line)]


def event_stops(state: GateState, benign: AbstractSet[str]) -> Sequence[Stop]:
    """The stops of the events since the newest review.

    Args:
        state: the typed state.
        benign: the kinds that leave the review current.

    Returns:
        A stop for a label pitboss does not apply, and for an event that makes
        the review of an older state.
    """
    timeline, attempts = listed(state.reads.timeline), state.attempts
    since = timeline[timeline.index(attempts[-1]) + 1 :] if attempts else []
    return [stop for event in since for stop in _event_stop(event, benign)]
