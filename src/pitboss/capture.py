"""Capturing the timeline of a PR as data a scenario replays (pitboss#444).

A scenario test replays what GitHub recorded of a real PR (keyword: scenario),
so the capture keeps only the fields the review flow reads: the PR, its
comments and reviews, its label and draft events, the commits that made its
heads and the check runs of each. Every list is read to its end: a capture
that stopped at a page would replay a shorter history than the PR had.
"""

import json
from typing import Mapping, Sequence

from . import ghapi

Item = Mapping[str, object]
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
EDIT_KEYS = ("created_at", "editor", "body")
EDITS_QUERY = (
    "query($owner: String!, $name: String!, $number: Int!) {"
    " repository(owner: $owner, name: $name) { pullRequest(number: $number) {"
    " userContentEdits(first: 100) { nodes { createdAt editor { login } diff }"
    " } } } }"
)
EVENTS = ("labeled", "unlabeled", "ready_for_review", "convert_to_draft")


def as_object(value: object) -> Item:
    """A JSON object as a mapping.

    Args:
        value: what the API gave where an object is.

    Returns:
        The object.
    """
    assert isinstance(value, dict)
    return value


def _items(value: object) -> Sequence[Item]:
    assert isinstance(value, list)
    return value


def _kept(item: Item, keys: Sequence[str]) -> Item:
    return {key: item.get(key) for key in keys}


def compact_pull(data: Item) -> Item:
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
        "user": {"login": as_object(data["user"])["login"]},
        "head": {
            "sha": as_object(data["head"])["sha"],
            "ref": as_object(data["head"])["ref"],
        },
        "base": {"ref": as_object(data["base"])["ref"]},
        "mergeable_state": data.get("mergeable_state"),
        "auto_merge": data.get("auto_merge"),
        "labels": [{"name": each["name"]} for each in _items(data.get("labels") or [])],
    }


def compact_event(data: Item) -> Item:
    """The fields of a label or draft event of the PR.

    Args:
        data: the API's issue event.

    Returns:
        The event name, its time and the label it names, if any.
    """
    label = _inner(data, "label", "name")
    return {
        "event": data["event"],
        "created_at": data["created_at"],
        "label": label,
    }


def compact_commit(data: Item) -> Item:
    """The sha and time of a commit of the PR.

    Args:
        data: the API's commit.

    Returns:
        The sha and the committer's date.
    """
    committer = as_object(as_object(data["commit"])["committer"])
    return {"sha": data["sha"], "date": committer["date"]}


def _list(github: ghapi.GitHub, path: str) -> Sequence[Item]:
    return ghapi.pages(github, path, json.loads)


def _checks(github: ghapi.GitHub, slug: str, sha: str) -> Sequence[Item]:
    path = f"repos/{slug}/commits/{sha}/check-runs"
    runs = ghapi.pages(github, path, lambda text: json.loads(text)["check_runs"])
    return [_kept(each, CHECK_KEYS) for each in runs]


def _kept_list(github: ghapi.GitHub, path: str, keys: Sequence[str]) -> Sequence[Item]:
    return [_kept(each, keys) for each in _list(github, path)]


def _events(github: ghapi.GitHub, base: str) -> Sequence[Item]:
    listed = _list(github, f"{base}/events")
    return [compact_event(each) for each in listed if each["event"] in EVENTS]


def _commits(github: ghapi.GitHub, base: str) -> Sequence[Item]:
    return [compact_commit(each) for each in _list(github, f"{base}/commits")]


def _all_checks(github: ghapi.GitHub, slug: str, commits: Sequence[Item]) -> Item:
    return {
        str(each["sha"]): _checks(github, slug, str(each["sha"]))
        for each in commits[-COMMIT_LIMIT:]
    }


def body_edits(data: Item) -> Sequence[Item]:
    """The body of a PR after each of its edits (keyword: body-edits).

    Args:
        data: GraphQL's answer for the PR (``data.repository.pullRequest``
            with ``userContentEdits.nodes``), newest edit first; each node's
            ``diff`` is the whole body as that edit left it.

    Returns:
        One item for each edit, oldest first (edits of one second keep their
        order): the time, the editor's login and the body after the edit.
    """
    pull = as_object(as_object(as_object(data["data"])["repository"])["pullRequest"])
    nodes = _items(as_object(pull["userContentEdits"])["nodes"])
    return [_edit(each) for each in reversed(nodes)]


def _edit(node: Item) -> Item:
    values = (node["createdAt"], _inner(node, "editor", "login"), node["diff"] or "")
    return dict(zip(EDIT_KEYS, values))


def _inner(node: Item, key: str, field: str) -> object:
    return as_object(node.get(key) or {}).get(field)


def live_edits(github: ghapi.GitHub, slug: str, number: int) -> Item:
    """Read the edits of a PR's body from GraphQL.

    Args:
        github: the API.
        slug: the PR's repository, ``owner/name``.
        number: its number.

    Returns:
        GraphQL's answer, as ``body_edits`` reads it.
    """
    owner, name = slug.split("/")
    command = ["gh", "api", "graphql", "-F", f"owner={owner}", "-F", f"name={name}"]
    command += ["-F", f"number={number}", "-f", f"query={EDITS_QUERY}"]
    return as_object(json.loads(github.run(command).stdout))


def _posted(github: ghapi.GitHub, base: str, number: int) -> Item:
    return {
        "comments": _kept_list(
            github, f"{base}/issues/{number}/comments", COMMENT_KEYS
        ),
        "reviews": _kept_list(github, f"{base}/pulls/{number}/reviews", REVIEW_KEYS),
        "events": _events(github, f"{base}/issues/{number}"),
    }


def capture(
    github: ghapi.GitHub, slug: str, number: int, edits: Sequence[Item]
) -> Item:
    """Read the whole recorded timeline of a PR.

    Args:
        github: the API.
        slug: the PR's repository, ``owner/name``.
        number: its number.
        edits: the body after each edit, as ``body_edits`` gives them.

    Returns:
        The timeline, ready to be written as JSON.
    """
    base = f"repos/{slug}"
    pull = json.loads(ghapi.get(github, f"{base}/pulls/{number}"))
    commits = _commits(github, f"{base}/pulls/{number}")
    return {
        "slug": slug,
        "number": number,
        "pull": compact_pull(pull),
        "body_edits": list(edits),
        **_posted(github, base, number),
        "commits": commits,
        "checks": _all_checks(github, slug, commits),
    }
