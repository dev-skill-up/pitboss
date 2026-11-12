"""Parsing GitHub's response bodies into ``shapes``."""

import json
import re
from typing import AbstractSet, Sequence

from . import shapes

FAILURE = "failure"


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


def pulls_of(items: Sequence[object]) -> Sequence[shapes.Pull]:
    """Parse pull requests GitHub listed.

    Args:
        items: each PR as listed.

    Returns:
        The pull requests, in order.
    """
    return [pull(json.dumps(item)) for item in items]


def labels(text: str) -> AbstractSet[str]:
    """Parse the labels of a pull request.

    Args:
        text: the response body of ``pulls/<number>``.

    Returns:
        The names of its labels.
    """
    listed = json.loads(text).get("labels", ())
    return frozenset(str(label["name"]) for label in listed)


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
            merged_at=item.get("merged_at") or "",
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
            head_sha=item.get("head_sha") or "",
            started_at=item.get("started_at") or "",
            completed_at=item.get("completed_at") or "",
            run=run_of(item.get("details_url")),
            succeeded=item.get("conclusion") == "success",
        )
        for item in json.loads(text)["check_runs"]
    ]


def run_of(url: str | None) -> int:
    """The Actions run id in a check run's or a status's URL.

    Args:
        url: ``.../actions/runs/<id>`` with or without a job (or None).

    Returns:
        The id, or 0 when the URL names no run.
    """
    found = re.search(r"/actions/runs/(\d+)", url or "")
    return int(found.group(1)) if found else 0


def statuses(text: str) -> Sequence[shapes.CommitStatus]:
    """Parse a page of a commit's combined status (the newest of each context).

    Args:
        text: the response body of ``commits/<sha>/status``.

    Returns:
        The statuses.
    """
    return [
        shapes.CommitStatus(
            context=item["context"],
            succeeded=item["state"] == "success",
            created_at=item.get("created_at") or "",
            run=run_of(item.get("target_url")),
            state=item["state"],
            description=item.get("description") or "",
            url=item.get("target_url") or "",
        )
        for item in json.loads(text)["statuses"]
    ]


def run_path(text: str) -> str:
    """Parse the workflow file a run belongs to.

    Args:
        text: the response body of ``actions/runs/<id>``.

    Returns:
        Its ``path`` (``.github/workflows/text-lint.yml``).
    """
    return str(json.loads(text).get("path") or "")


def failed_steps(text: str) -> Sequence[str]:
    """Parse the names of the failed steps of a job.

    Args:
        text: the response body of ``actions/jobs/<id>``.

    Returns:
        The names of its steps that failed.
    """
    steps = json.loads(text).get("steps") or []
    return [step["name"] for step in steps if step.get("conclusion") == FAILURE]


def output_text(text: str) -> tuple[str, str]:
    """Parse a check run's output title and summary.

    Args:
        text: the response body of ``check-runs/<id>``.

    Returns:
        The title and the summary (empty when it has none).
    """
    output = json.loads(text).get("output") or {}
    return output.get("title") or "", output.get("summary") or ""


def annotations(text: str) -> Sequence[str]:
    """Parse the failure annotations of a check run.

    Warnings and notices (such as an action's deprecation notice) are left out.

    Args:
        text: the response body of ``check-runs/<id>/annotations``.

    Returns:
        Each as ``path:line: message``.
    """
    failures = [
        item for item in json.loads(text) if item.get("annotation_level") == FAILURE
    ]
    return [
        f"{item.get('path') or ''}:{item.get('start_line') or 0}:"
        f" {item.get('message') or ''}"
        for item in failures
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
            url=item.get("html_url") or "",
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


def window_runs(text: str) -> Sequence[shapes.WindowRun]:
    """Parse a page of a workflow's runs, with the commit and PRs of each.

    Args:
        text: the response body of ``workflows/<workflow>/runs``.

    Returns:
        The runs.
    """
    return [
        shapes.WindowRun(
            id=item["id"],
            url=item["html_url"],
            conclusion=item.get("conclusion") or "",
            created_at=item["created_at"],
            branch=item.get("head_branch") or "",
            head_sha=item["head_sha"],
            pulls=tuple(pull["number"] for pull in item.get("pull_requests") or []),
            event=item["event"],
            updated_at=item["updated_at"],
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


def timeline_events(text: str) -> Sequence[shapes.TimelineEvent]:
    """Parse a page of a PR's timeline, every event, so a page's length pages.

    Args:
        text: the response body of ``issues/<number>/timeline``.

    Returns:
        The events in the order GitHub gives them (oldest first).
    """
    return [
        shapes.TimelineEvent(
            kind=item.get("event") or "", at=item.get("created_at") or ""
        )
        for item in json.loads(text)
    ]


def job_results(text: str) -> Sequence[shapes.JobResult]:
    """Parse a page of the jobs of a run, with the failed steps of each.

    Args:
        text: the response body of ``actions/runs/<id>/jobs``.

    Returns:
        Every job.
    """
    return [
        shapes.JobResult(
            name=item["name"],
            conclusion=item.get("conclusion") or "",
            failed_steps=[
                step["name"]
                for step in item.get("steps") or []
                if step.get("conclusion") == FAILURE
            ],
        )
        for item in json.loads(text)["jobs"]
    ]
