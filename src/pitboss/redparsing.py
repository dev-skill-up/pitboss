"""Parsing the response bodies the red-run analysis reads."""

import json
from typing import Mapping, Sequence

from . import redshapes


def _text(data: Mapping[str, object], key: str) -> str:
    return str(data.get(key) or "")


def _step(data: Mapping[str, object]) -> redshapes.Step:
    return redshapes.Step(
        number=int(str(data["number"])),
        name=str(data["name"]),
        conclusion=_text(data, "conclusion"),
        started_at=_text(data, "started_at"),
        completed_at=_text(data, "completed_at"),
    )


def jobs(text: str) -> Sequence[redshapes.Job]:
    """Parse a page of a run's jobs.

    Args:
        text: the response body of ``actions/runs/<id>/jobs``.

    Returns:
        The jobs.
    """
    return [
        redshapes.Job(
            id=item["id"],
            name=item["name"],
            conclusion=_text(item, "conclusion"),
            url=item["html_url"],
            started_at=_text(item, "started_at"),
            completed_at=_text(item, "completed_at"),
            steps=[_step(step) for step in item.get("steps") or []],
        )
        for item in json.loads(text)["jobs"]
    ]


def pull_state(text: str) -> redshapes.PullState:
    """Parse a pull request into what became of it.

    Args:
        text: the response body of ``pulls/<number>``.

    Returns:
        Its state.
    """
    data = json.loads(text)
    return redshapes.PullState(
        number=data["number"],
        title=data["title"],
        url=data["html_url"],
        merged=data.get("merged_at") is not None,
        state=data["state"],
    )


def pull_commits(text: str) -> Sequence[redshapes.FixCommit]:
    """Parse a page of a PR's commits (without their files).

    Args:
        text: the response body of ``pulls/<number>/commits``.

    Returns:
        The commits, oldest first.
    """
    return [
        redshapes.FixCommit(
            sha=item["sha"],
            message=item["commit"]["message"],
            date=item["commit"]["committer"]["date"],
            merge=len(item.get("parents") or []) > 1,
            files=[],
        )
        for item in json.loads(text)
    ]


def commit_files(text: str) -> Sequence[str]:
    """Parse the files a commit changes.

    Args:
        text: the response body of ``commits/<sha>``.

    Returns:
        The file names.
    """
    return [item["filename"] for item in json.loads(text).get("files") or []]
