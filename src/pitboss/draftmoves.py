"""A change of a PR's draft state after the sweep marked it ready (keyword: draft-moves).

(Pitboss#355.) On 2026-11-08 a worker converted a Plan-approved PR back to draft,
and the timeline named the shared ``moshez`` account, so the owner was blamed.
Only the sweep marks a PR ready, so its first ``ready_for_review`` event is the
sweep's own state change; a later ``convert_to_draft`` or ``ready_for_review``
event is not the sweep's and is told with its time. The newest one is told.
"""

import subprocess
from typing import Sequence

from . import ghapi, parsing, pulls, shapes
from .markers import Marker

READY = "ready_for_review"
STATE_EVENTS = ("convert_to_draft", READY)
ACTOR = (
    "actor `moshez` is the shared agent account; check the workers' rounds before"
    " naming anyone"
)


def after_marked_ready(
    events: Sequence[shapes.TimelineEvent],
) -> shapes.TimelineEvent | None:
    """The newest draft-state event after the first ``ready_for_review``.

    Args:
        events: the PR's timeline, oldest first.

    Returns:
        The event; None when the PR was never marked ready or nothing followed.
    """
    changes = [each for each in events if each.kind in STATE_EVENTS]
    ready = [index for index, each in enumerate(changes) if each.kind == READY]
    later = changes[ready[0] + 1 :] if ready else []
    return later[-1] if later else None


def line(pull: pulls.PullFacts, event: shapes.TimelineEvent) -> str:
    """The line of a draft-state change that was not the sweep's.

    Args:
        pull: the PR.
        event: the change.

    Returns:
        The line.
    """
    return (
        f"{Marker.DRAFT_STATE_CHANGED.text} {pulls.reference(pull)}: {event.kind}"
        f" at {event.at} came after the sweep marked the PR ready; {ACTOR}"
    )


def tell(github: ghapi.GitHub, pull: pulls.PullFacts) -> Sequence[str]:
    """Read a PR's timeline and say a draft-state change that was not the sweep's.

    Args:
        github: the API.
        pull: the PR.

    Returns:
        The line, none when there is nothing to say; a timeline that cannot be
        read says nothing (the merge queue's line, where it applies, says
        UNREADABLE for the same call).
    """
    try:
        events = ghapi.pages(
            github,
            f"repos/{pull.repo.slug}/issues/{pull.pull.number}/timeline",
            parsing.timeline_events,
        )
    except subprocess.CalledProcessError:
        return []
    found = after_marked_ready(events)
    return [] if found is None else [line(pull, found)]
