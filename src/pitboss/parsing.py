"""Parsing GitHub's response bodies into ``shapes``."""

import json
from typing import Sequence

from . import shapes


def _each(text: str, key: str) -> Sequence[str]:
    return [str(item[key]) for item in json.loads(text)]


def _finished(status: str) -> bool:
    return status in shapes.FINISHED_STATUSES


def pull(text: str) -> shapes.Pull:
    """Parse a pull request.

    Args:
        text: the response body of ``pulls/<number>``.

    Returns:
        The pull request.
    """
    data = json.loads(text)
    return shapes.Pull(
        number=data["number"],
        title=data["title"],
        created_at=data["created_at"],
        draft=bool(data.get("draft")),
        author=data["user"]["login"],
        body=data.get("body") or "",
        head=shapes.Head(sha=data["head"]["sha"], branch=data["head"]["ref"]),
        base=data["base"]["ref"],
        mergeable_state=shapes.MERGE_STATES.get(
            data.get("mergeable_state") or "", shapes.MergeState.UNKNOWN
        ),
        auto_merge=data.get("auto_merge") is not None,
    )


def pull_numbers(text: str) -> Sequence[int]:
    """Parse a page of pull requests into their numbers.

    Args:
        text: the response body of ``pulls``.

    Returns:
        The numbers.
    """
    return [int(number) for number in _each(text, "number")]


def outcomes(text: str) -> Sequence[shapes.Outcome]:
    """Parse a page of pull requests into what became of their branches.

    Args:
        text: the response body of ``pulls?state=all``.

    Returns:
        The outcomes.
    """
    return [
        shapes.Outcome(
            branch=item["head"]["ref"],
            still_open=item["state"] == "open",
            merged=item.get("merged_at") is not None,
        )
        for item in json.loads(text)
    ]


def check_runs(text: str) -> Sequence[shapes.CheckRun]:
    """Parse a page of check runs.

    Args:
        text: the response body of ``commits/<sha>/check-runs``.

    Returns:
        The check runs.
    """
    return [
        shapes.CheckRun(
            id=item["id"],
            name=item["name"],
            finished=_finished(item["status"]),
            failed=item.get("conclusion") in shapes.FAILED_CONCLUSIONS,
        )
        for item in json.loads(text)["check_runs"]
    ]


def comments(text: str) -> Sequence[shapes.Comment]:
    """Parse a page of issue comments.

    Args:
        text: the response body of ``issues/<number>/comments``.

    Returns:
        The comments.
    """
    return [
        shapes.Comment(
            body=item.get("body") or "",
            author_association=item["author_association"],
            created_at=item["created_at"],
        )
        for item in json.loads(text)
    ]


def reviews(text: str) -> Sequence[shapes.PullReview]:
    """Parse a page of pull request reviews.

    Args:
        text: the response body of ``pulls/<number>/reviews``.

    Returns:
        The reviews.
    """
    return [
        shapes.PullReview(
            state=item["state"],
            commit_id=item["commit_id"],
            author_association=item["author_association"],
            submitted_at=item.get("submitted_at") or "",
        )
        for item in json.loads(text)
    ]


def comparison(text: str) -> Sequence[shapes.Commit]:
    """Parse a comparison.

    Args:
        text: the response body of ``compare/<base>...<head>``.

    Returns:
        The commits of the comparison.
    """
    return [
        shapes.Commit(sha=item["sha"], parents=len(item["parents"]))
        for item in json.loads(text)["commits"]
    ]


def workflow_runs(text: str) -> Sequence[shapes.WorkflowRun]:
    """Parse a page of workflow runs.

    Args:
        text: the response body of ``actions/runs``.

    Returns:
        The runs.
    """
    return [
        shapes.WorkflowRun(
            id=item["id"],
            status=item["status"],
            conclusion=item.get("conclusion"),
            finished=_finished(item["status"]),
            created_at=item["created_at"],
            head_branch=item.get("head_branch") or "",
        )
        for item in json.loads(text)["workflow_runs"]
    ]


def jobs_waiting(text: str) -> Sequence[bool]:
    """Parse a page of jobs into whether each waits for a runner.

    Args:
        text: the response body of ``actions/runs/<id>/jobs``.

    Returns:
        For each job, whether it is still queued.
    """
    return [
        item["status"] in shapes.WAITING_STATUSES for item in json.loads(text)["jobs"]
    ]


def issues(text: str) -> Sequence[shapes.Issue]:
    """Parse a page of issues, leaving out PRs (which the list includes).

    Args:
        text: the response body of ``issues``.

    Returns:
        The issues.
    """
    return [
        shapes.Issue(
            number=item["number"],
            title=item["title"],
            created_at=item["created_at"],
            labels=frozenset(label["name"] for label in item["labels"]),
            body=item.get("body") or "",
        )
        for item in json.loads(text)
        if "pull_request" not in item
    ]
