"""Capturing the timeline of a PR as data a scenario replays (pitboss#444).

A scenario test replays what GitHub recorded of a real PR (keyword: scenario),
so the capture keeps only the fields the review flow reads: the PR, its
comments and reviews, its label and draft events, the commits that made its
heads and the check runs of each. Every list is read to its end: a capture
that stopped at a page would replay a shorter history than the PR had.
"""

import json
from typing import Any, Mapping, Sequence

from . import ghapi

COMMIT_LIMIT = 100
PULL_KEYS = ("number", "title", "created_at", "updated_at", "state", "merged_at")
COMMENT_KEYS = ("id", "body", "author_association", "created_at", "html_url")
REVIEW_KEYS = ("state", "commit_id", "author_association", "submitted_at")
CHECK_KEYS = (
    "id",
    "name",
    "status",
    "conclusion",
    "head_sha",
    "started_at",
    "completed_at",
    "details_url",
)
EVENTS = ("labeled", "unlabeled", "ready_for_review", "convert_to_draft")


def _kept(item: Mapping[str, Any], keys: Sequence[str]) -> Mapping[str, Any]:
    return {key: item.get(key) for key in keys}


def compact_pull(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """The fields of a PR the flow reads.

    Args:
        data: the API's PR.

    Returns:
        The PR, with its author, head, base, labels and merge state flattened.
    """
    return {
        **_kept(data, PULL_KEYS),
        "body": data.get("body") or "",
        "draft": bool(data.get("draft")),
        "user": {"login": data["user"]["login"]},
        "head": {"sha": data["head"]["sha"], "ref": data["head"]["ref"]},
        "base": {"ref": data["base"]["ref"]},
        "mergeable_state": data.get("mergeable_state"),
        "auto_merge": data.get("auto_merge"),
        "labels": [{"name": each["name"]} for each in data.get("labels", ())],
    }


def compact_event(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """The fields of a label or draft event of the PR.

    Args:
        data: the API's issue event.

    Returns:
        The event name, its time and the label it names, if any.
    """
    label = (data.get("label") or {}).get("name")
    return {
        "event": data["event"],
        "created_at": data["created_at"],
        "label": label,
    }


def compact_commit(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """The sha and time of a commit of the PR.

    Args:
        data: the API's commit.

    Returns:
        The sha and the committer's date.
    """
    return {"sha": data["sha"], "date": data["commit"]["committer"]["date"]}


def _list(github: ghapi.GitHub, path: str) -> Sequence[Mapping[str, Any]]:
    return ghapi.pages(github, path, json.loads)


def _checks(github: ghapi.GitHub, slug: str, sha: str) -> Sequence[Mapping[str, Any]]:
    path = f"repos/{slug}/commits/{sha}/check-runs"
    runs = ghapi.pages(github, path, lambda text: json.loads(text)["check_runs"])
    return [_kept(each, CHECK_KEYS) for each in runs]


def capture(github: ghapi.GitHub, slug: str, number: int) -> Mapping[str, Any]:
    """Read the whole recorded timeline of a PR.

    Args:
        github: the API.
        slug: the PR's repository, ``owner/name``.
        number: its number.

    Returns:
        The timeline, ready to be written as JSON.
    """
    base = f"repos/{slug}"
    pull = json.loads(ghapi.get(github, f"{base}/pulls/{number}"))
    commits = [
        compact_commit(each)
        for each in _list(github, f"{base}/pulls/{number}/commits")
    ]
    kept = [each for each in _list(github, f"{base}/issues/{number}/events")]
    return {
        "slug": slug,
        "number": number,
        "pull": compact_pull(pull),
        "comments": [
            {**_kept(each, COMMENT_KEYS)}
            for each in _list(github, f"{base}/issues/{number}/comments")
        ],
        "reviews": [
            _kept(each, REVIEW_KEYS)
            for each in _list(github, f"{base}/pulls/{number}/reviews")
        ],
        "events": [compact_event(each) for each in kept if each["event"] in EVENTS],
        "commits": commits,
        "checks": {
            each["sha"]: _checks(github, slug, each["sha"])
            for each in commits[-COMMIT_LIMIT:]
        },
    }
