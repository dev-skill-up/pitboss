"""The stops of the events since the newest review (keyword: gate).

A label pitboss does not apply, and any event that is not benign, make the newest
review one of an older state (pitboss#444, the act verdict's row of the timeline).
"""

import functools
from typing import AbstractSet, Sequence

from . import enumeration, totalreview
from .gatestop import Route, Stop
from .totalanswer import KNOWN_LABELS
from .totaljson import JsonMap, listed, name_at

LABEL_EVENTS = frozenset({"labeled", "unlabeled"})


@functools.cache
def stale_events() -> AbstractSet[str]:
    """The documented timeline kinds after which the newest review is stale.

    Returns:
        The kinds of ``enumeration/stale-events.txt``.
    """
    return frozenset(enumeration.shipped("stale-events.txt").split())


def _event_stop(event: JsonMap, benign: AbstractSet[str]) -> Sequence[Stop]:
    # a label pitboss does not apply, or an event after which the review is stale
    kind = event.get("event")
    if kind in LABEL_EVENTS:
        label = name_at(event, "label", "name")
        if label in KNOWN_LABELS:
            return []
        line = f"event {kind} {label or None}: a label pitboss does not apply"
        return [Stop(route=Route.LABEL, line=line)]
    if kind in benign:
        return []
    line = f"event {kind}: the review is of an older state; review again"
    return [Stop(route=Route.REVIEW, line=line)]


def event_stops(ctx: JsonMap, benign: AbstractSet[str]) -> Sequence[Stop]:
    """The stops of the events since the newest review.

    Args:
        ctx: the inputs.
        benign: the kinds that leave the review current.

    Returns:
        A stop for a label pitboss does not apply, and for an event that makes
        the review of an older state.
    """
    timeline = listed(ctx, "timeline")
    attempts = totalreview.review_attempts(timeline)
    since = timeline[timeline.index(attempts[-1]) + 1 :] if attempts else []
    return [stop for event in since for stop in _event_stop(event, benign)]
