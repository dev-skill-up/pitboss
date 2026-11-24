"""Parsing GitHub's response bodies into ``shapes``."""

import json
import re
from typing import AbstractSet, Mapping, Sequence

from . import checkoutcome, shapes, totaljson
from .totaljson import text as text_of

FAILURE = "failure"


def _head(data: totaljson.JsonMap) -> shapes.Head:
    sha, branch = (totaljson.name_at(data, "head", key) for key in ("sha", "ref"))
    return shapes.Head(sha=sha, branch=branch, repo="")


def pull(text: str) -> shapes.Pull:
    """Parse a pull request.

    Args:
        text: the response body of ``pulls/<number>``.

    Returns:
        The pull request.
    """
    data = totaljson.whole(text)
    return shapes.Pull(
        number=totaljson.count(data, "number"),
        title=text_of(data.get("title")),
        created_at=text_of(data.get("created_at")),
        draft=bool(data.get("draft")),
        author=totaljson.name_at(data, "user", "login"),
        body=text_of(data.get("body")),
        head=_head(data),
        base=totaljson.name_at(data, "base", "ref"),
        mergeable_state=shapes.MERGE_STATES.get(
            text_of(data.get("mergeable_state")), shapes.MergeState.UNKNOWN
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
    return frozenset(
        text_of(each.get("name")) for each in totaljson.rows(text, "labels")
    )


def pull_numbers(text: str) -> Sequence[int]:
    """Parse a page of pull requests into their numbers.

    Args:
        text: the response body of ``pulls``.

    Returns:
        The numbers.
    """
    return [totaljson.count(item, "number") for item in totaljson.rows(text)]


def outcomes(text: str) -> Sequence[shapes.Outcome]:
    """Parse a page of pull requests into what became of their branches.

    Args:
        text: the response body of a page of ``pulls``, open or closed.

    Returns:
        The outcomes.
    """
    return [
        shapes.Outcome(
            branch=totaljson.name_at(item, "head", "ref"),
            still_open=item.get("state") == "open",
            merged=item.get("merged_at") is not None,
            merged_at=text_of(item.get("merged_at")),
        )
        for item in totaljson.rows(text)
    ]


CHECK_TEXTS = ("name", "head_sha", "started_at", "completed_at", "details_url")


def check_runs(text: str) -> Sequence[shapes.CheckRun]:
    """Parse a page of check runs.

    Args:
        text: the response body of ``commits/<sha>/check-runs``.

    Returns:
        The check runs.
    """
    return [one_check(item) for item in totaljson.rows(text, "check_runs")]


def _login(item: Mapping[str, object]) -> str:
    # the author's login, empty when GitHub gives no user
    return totaljson.name_at(item, "user", "login")


def one_check(item: Mapping[str, object]) -> shapes.CheckRun:
    """One check run, as GitHub answers it: its outcome by ``checkoutcome``.

    Args:
        item: the check run's object.

    Returns:
        The check run.
    """
    conclusion, status = item.get("conclusion"), text_of(item.get("status"))
    words = {key: text_of(item.get(key)) for key in CHECK_TEXTS}
    return shapes.CheckRun(
        id=totaljson.count(item, "id"),
        finished=checkoutcome.finished(status),
        failed=checkoutcome.failed(status, conclusion),
        name=words["name"],
        head_sha=words["head_sha"],
        started_at=words["started_at"],
        completed_at=words["completed_at"],
        run=run_of(words["details_url"] or None),
        succeeded=conclusion == "success",
        said=(status, str(conclusion)),  # keyword: gate
    )


def run_of(url: str | None) -> int:
    """The Actions run id in a check run's or a status's URL.

    Args:
        url: ``.../actions/runs/<id>`` with or without a job (or None).

    Returns:
        The id, or 0 when the URL names no run.
    """
    found = re.search(r"/actions/runs/(\d+)", url or "")
    return int(found.string[found.start(1) : found.end(1)]) if found else 0


def statuses(text: str) -> Sequence[shapes.CommitStatus]:
    """Parse a page of a commit's combined status (the newest of each context).

    Args:
        text: the response body of ``commits/<sha>/status``.

    Returns:
        The statuses.
    """
    return [
        shapes.CommitStatus(
            context=text_of(item.get("context")),
            succeeded=item.get("state") == "success",
            created_at=text_of(item.get("created_at")),
            run=run_of(text_of(item.get("target_url"))),
            state=text_of(item.get("state")),
            description=text_of(item.get("description")),
            url=text_of(item.get("target_url")),
        )
        for item in totaljson.rows(text, "statuses")
    ]


def run_path(text: str) -> str:
    """Parse the workflow file a run belongs to.

    Args:
        text: the response body of ``actions/runs/<id>``.

    Returns:
        Its ``path`` (``.github/workflows/text-lint.yml``).
    """
    return totaljson.name_at(totaljson.read(text), "path")


def failed_steps(text: str) -> Sequence[str]:
    """Parse the names of the failed steps of a job.

    Args:
        text: the response body of ``actions/jobs/<id>``.

    Returns:
        The names of its steps that failed.
    """
    steps = totaljson.rows(text, "steps")
    return [
        text_of(step.get("name")) for step in steps if step.get("conclusion") == FAILURE
    ]


def output_text(text: str) -> tuple[str, str]:
    """Parse a check run's output title and summary.

    Args:
        text: the response body of ``check-runs/<id>``.

    Returns:
        The title and the summary (empty when it has none).
    """
    title, summary = (
        totaljson.name_at(totaljson.read(text), "output", key)
        for key in ("title", "summary")
    )
    return title, summary


def annotations(text: str) -> Sequence[str]:
    """Parse the failure annotations of a check run.

    Warnings and notices (such as an action's deprecation notice) are left out.

    Args:
        text: the response body of ``check-runs/<id>/annotations``.

    Returns:
        Each as ``path:line: message``.
    """
    failures = [
        item for item in totaljson.rows(text) if item.get("annotation_level") == FAILURE
    ]
    return [
        f"{text_of(item.get('path'))}:{totaljson.count(item, 'start_line')}:"
        f" {text_of(item.get('message'))}"
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
            body=text_of(item.get("body")),
            author_association=text_of(item.get("author_association")),
            created_at=text_of(item.get("created_at")),
            url=text_of(item.get("html_url")),
            login=_login(item),
        )
        for item in totaljson.rows(text)
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
            state=text_of(item.get("state")),
            commit_id=text_of(item.get("commit_id")),
            author_association=text_of(item.get("author_association")),
            submitted_at=text_of(item.get("submitted_at")),
            body=text_of(item.get("body")),
            login=_login(item),
        )
        for item in totaljson.rows(text)
    ]


def comparison(text: str) -> Sequence[shapes.Commit]:
    """Parse a comparison.

    Args:
        text: the response body of ``compare/<base>...<head>``.

    Returns:
        The commits of the comparison.
    """
    return [
        shapes.Commit(
            sha=text_of(item.get("sha")),
            parents=len(totaljson.listing(item.get("parents"))),
        )
        for item in totaljson.rows(text, "commits")
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
            id=totaljson.count(item, "id"),
            status=text_of(item.get("status")),
            conclusion=text_of(item.get("conclusion")) or None,
            finished=checkoutcome.finished(text_of(item.get("status"))),
            created_at=text_of(item.get("created_at")),
            head_branch=text_of(item.get("head_branch")),
        )
        for item in totaljson.rows(text, "workflow_runs")
    ]


def _numbers(listed: object) -> tuple[int, ...]:
    return tuple(totaljson.count(each, "number") for each in totaljson.records(listed))


def window_runs(text: str) -> Sequence[shapes.WindowRun]:
    """Parse a page of a workflow's runs, with the commit and PRs of each.

    Args:
        text: the response body of ``workflows/<workflow>/runs``.

    Returns:
        The runs.
    """
    return [_window_run(item) for item in totaljson.rows(text, "workflow_runs")]


def _window_run(item: totaljson.JsonMap) -> shapes.WindowRun:
    return shapes.WindowRun(
        id=totaljson.count(item, "id"),
        url=text_of(item.get("html_url")),
        conclusion=text_of(item.get("conclusion")),
        created_at=text_of(item.get("created_at")),
        branch=text_of(item.get("head_branch")),
        head_sha=text_of(item.get("head_sha")),
        pulls=_numbers(item.get("pull_requests")),
        event=text_of(item.get("event")),
        updated_at=text_of(item.get("updated_at")),
    )


def jobs_waiting(text: str) -> Sequence[bool]:
    """Parse a page of jobs into whether each waits for a runner.

    Args:
        text: the response body of ``actions/runs/<id>/jobs``.

    Returns:
        For each job, whether it is still queued.
    """
    return [
        text_of(item.get("status")) in shapes.WAITING_STATUSES
        for item in totaljson.rows(text, "jobs")
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
            kind=text_of(item.get("event")), at=text_of(item.get("created_at"))
        )
        for item in totaljson.rows(text)
    ]
