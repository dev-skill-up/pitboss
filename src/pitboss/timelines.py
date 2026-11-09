"""Reading the timeline of a PR (keyword: timeline)."""

from typing import Sequence

from . import ghapi, parsing, shapes


def read(
    github: ghapi.GitHub, slug: str, number: int
) -> Sequence[shapes.TimelineEvent]:
    """Read every event of a PR's timeline.

    Args:
        github: the API.
        slug: the PR's repository, ``owner/name``.
        number: the PR's number.

    Returns:
        The events, oldest first.
    """
    path = f"repos/{slug}/issues/{number}/timeline"
    return ghapi.pages(github, path, parsing.timeline_events)
