"""The PRs merged lately, for the task list (keyword: tasklist-state, pitboss#471)."""

import datetime
import json
import subprocess
from typing import Sequence

from . import config, ghapi

WINDOW = datetime.timedelta(hours=24)


def lately(
    github: ghapi.GitHub, settings: config.Config, now: datetime.datetime
) -> Sequence[str]:
    """The PRs of the project's repository merged in the last day.

    Args:
        github: the API.
        settings: the configuration.
        now: the time now.

    Returns:
        ``owner/name#number`` of each, newest first; none when GitHub cannot say.
    """
    repo = settings.project.repo
    slug = repo.slug
    path = f"repos/{slug}/pulls?state=closed&sort=updated&direction=desc"
    try:
        listed = json.loads(ghapi.get(github, f"{path}&per_page=30"))
    except (subprocess.CalledProcessError, ValueError):
        return []
    return [
        f"{slug}#{each['number']}"
        for each in listed
        if each.get("merged_at") and _since(each["merged_at"], now)
    ]


def _since(stamp: str, now: datetime.datetime) -> bool:
    merged = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return now - merged <= WINDOW
