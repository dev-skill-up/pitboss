"""The parts of GitHub's REST responses that pitboss reads.

Each parser turns one response body into frozen dataclasses, so nothing
past this module touches JSON.
"""

import dataclasses
import enum
import json
from typing import Sequence


FINISHED_STATUSES = frozenset({"completed"})
WAITING_STATUSES = frozenset({"queued"})
FAILED_CONCLUSIONS = frozenset(
    {"failure", "cancelled", "timed_out", "action_required", "startup_failure"}
)


class MergeState(enum.Enum):
    """A PR's ``mergeable_state`` (github-values); printed as its lowercase name.

    Attributes:
        BEHIND: the base moved on; it still queues.
        BLOCKED: checks pending or red, or a required review missing.
        CLEAN: mergeable, with every requirement met.
        DIRTY: a merge conflict.
        DRAFT: a draft.
        HAS_HOOKS: mergeable, with pre-receive hooks.
        UNKNOWN: GitHub is still computing it.
        UNSTABLE: mergeable, with non-required checks failing.
    """

    BEHIND = enum.auto()
    BLOCKED = enum.auto()
    CLEAN = enum.auto()
    DIRTY = enum.auto()
    DRAFT = enum.auto()
    HAS_HOOKS = enum.auto()
    UNKNOWN = enum.auto()
    UNSTABLE = enum.auto()


MERGE_STATES = {state.name.lower(): state for state in MergeState}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Head:
    """The branch a PR merges.

    Attributes:
        sha: its tip.
        branch: its name.
    """

    sha: str
    branch: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Pull:
    """A pull request, as its own URL gives it.

    Attributes:
        number: its number.
        title: its title.
        created_at: when it was opened (ISO 8601).
        draft: whether it is a draft.
        author: its author's login.
        body: its text.
        head: the branch it merges.
        base: the branch it merges into.
        mergeable_state: GitHub's merge state.
        auto_merge: whether auto-merge is armed.
    """

    number: int
    title: str
    created_at: str
    draft: bool
    author: str
    body: str
    head: Head
    base: str
    mergeable_state: MergeState
    auto_merge: bool


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Outcome:
    """What became of a PR's branch.

    Attributes:
        branch: the PR's branch.
        still_open: whether the PR is open.
        merged: whether it merged.
    """

    branch: str
    still_open: bool
    merged: bool


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class CheckRun:
    """A check run on a commit.

    Attributes:
        id: its id (for an Actions check, also its job's id).
        name: its name.
        finished: whether it completed.
        failed: whether it completed and failed.
    """

    id: int
    name: str
    finished: bool
    failed: bool


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Comment:
    """An issue comment.

    Attributes:
        body: its text.
        author_association: its author's relation to the repository.
        created_at: when it was written (ISO 8601).
    """

    body: str
    author_association: str
    created_at: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PullReview:
    """A GitHub pull request review.

    Attributes:
        state: ``APPROVED``, ``CHANGES_REQUESTED``, ``COMMENTED``, ...
        commit_id: the commit it reviewed.
        author_association: its author's relation to the repository.
        submitted_at: when it was submitted (ISO 8601).
    """

    state: str
    commit_id: str
    author_association: str
    submitted_at: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Commit:
    """A commit in a comparison.

    Attributes:
        sha: its SHA.
        parents: how many parents it has (two or more: a merge).
    """

    sha: str
    parents: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowRun:
    """A workflow run.

    Attributes:
        id: its id.
        status: its status.
        conclusion: its conclusion, once completed.
        finished: whether it completed.
        created_at: when it was created (ISO 8601).
        head_branch: the branch it ran on.
    """

    id: int
    status: str
    conclusion: str | None
    finished: bool
    created_at: str
    head_branch: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Issue:
    """An open issue.

    Attributes:
        number: its number.
        title: its title.
        created_at: when it was opened (ISO 8601).
        labels: its labels' names.
        body: its text.
    """

    number: int
    title: str
    created_at: str
    labels: frozenset[str]
    body: str


def pull(text: str) -> Pull:
    """Parse a pull request.

    Args:
        text: the response body of ``pulls/<number>``.

    Returns:
        The pull request.
    """
    data = json.loads(text)
    return Pull(
        number=data["number"],
        title=data["title"],
        created_at=data["created_at"],
        draft=bool(data.get("draft")),
        author=data["user"]["login"],
        body=data.get("body") or "",
        head=Head(sha=data["head"]["sha"], branch=data["head"]["ref"]),
        base=data["base"]["ref"],
        mergeable_state=MERGE_STATES.get(
            data.get("mergeable_state") or "", MergeState.UNKNOWN
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
    return [item["number"] for item in json.loads(text)]


def outcomes(text: str) -> Sequence[Outcome]:
    """Parse a page of pull requests into what became of their branches.

    Args:
        text: the response body of ``pulls?state=all``.

    Returns:
        The outcomes.
    """
    return [
        Outcome(
            branch=item["head"]["ref"],
            still_open=item["state"] == "open",
            merged=item.get("merged_at") is not None,
        )
        for item in json.loads(text)
    ]


def check_runs(text: str) -> Sequence[CheckRun]:
    """Parse a page of check runs.

    Args:
        text: the response body of ``commits/<sha>/check-runs``.

    Returns:
        The check runs.
    """
    return [
        CheckRun(
            id=item["id"],
            name=item["name"],
            finished=item["status"] in FINISHED_STATUSES,
            failed=item.get("conclusion") in FAILED_CONCLUSIONS,
        )
        for item in json.loads(text)["check_runs"]
    ]


def comments(text: str) -> Sequence[Comment]:
    """Parse a page of issue comments.

    Args:
        text: the response body of ``issues/<number>/comments``.

    Returns:
        The comments.
    """
    return [
        Comment(
            body=item.get("body") or "",
            author_association=item["author_association"],
            created_at=item["created_at"],
        )
        for item in json.loads(text)
    ]


def reviews(text: str) -> Sequence[PullReview]:
    """Parse a page of pull request reviews.

    Args:
        text: the response body of ``pulls/<number>/reviews``.

    Returns:
        The reviews.
    """
    return [
        PullReview(
            state=item["state"],
            commit_id=item["commit_id"],
            author_association=item["author_association"],
            submitted_at=item.get("submitted_at") or "",
        )
        for item in json.loads(text)
    ]


def comparison(text: str) -> Sequence[Commit]:
    """Parse a comparison.

    Args:
        text: the response body of ``compare/<base>...<head>``.

    Returns:
        The commits of the comparison.
    """
    return [
        Commit(sha=item["sha"], parents=len(item["parents"]))
        for item in json.loads(text)["commits"]
    ]


def workflow_runs(text: str) -> Sequence[WorkflowRun]:
    """Parse a page of workflow runs.

    Args:
        text: the response body of ``actions/runs``.

    Returns:
        The runs.
    """
    return [
        WorkflowRun(
            id=item["id"],
            status=item["status"],
            conclusion=item.get("conclusion"),
            finished=item["status"] in FINISHED_STATUSES,
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
    return [item["status"] in WAITING_STATUSES for item in json.loads(text)["jobs"]]


def issues(text: str) -> Sequence[Issue]:
    """Parse a page of issues, leaving out PRs (which the list includes).

    Args:
        text: the response body of ``issues``.

    Returns:
        The issues.
    """
    return [
        Issue(
            number=item["number"],
            title=item["title"],
            created_at=item["created_at"],
            labels=frozenset(label["name"] for label in item["labels"]),
            body=item.get("body") or "",
        )
        for item in json.loads(text)
        if "pull_request" not in item
    ]


def filenames(text: str) -> Sequence[str]:
    """Parse a page of a PR's files into their paths.

    Args:
        text: the response body of ``pulls/<number>/files``.

    Returns:
        The paths.
    """
    return [item["filename"] for item in json.loads(text)]
