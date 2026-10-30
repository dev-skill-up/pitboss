"""The parts of GitHub's REST responses that pitboss reads, as dataclasses.

``parsing`` builds them from response bodies, so nothing else touches JSON.
"""

import dataclasses
import enum
from typing import AbstractSet, Sequence

FINISHED_STATUSES = frozenset({"completed"})
WAITING_STATUSES = frozenset({"queued"})
# A cancelled check (concurrency cancel-in-progress) is superseded, not red;
# skipped and neutral ones are not here either.
FAILED_CONCLUSIONS = frozenset(
    {"failure", "timed_out", "action_required", "startup_failure"}
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
        head_sha: the commit it ran on ("" when GitHub does not say).
        started_at: when it started (ISO 8601, "" when it has not).
        completed_at: when it completed (ISO 8601, "" when it has not).
    """

    id: int
    name: str
    finished: bool
    failed: bool
    head_sha: str = ""
    started_at: str = ""
    completed_at: str = ""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Failure:
    """What api.github.com says about why a check failed.

    Attributes:
        steps: the names of the job's failed steps.
        title: the check run's output title.
        summary: the check run's output summary.
        annotations: each annotation as ``path:line: message``.
    """

    steps: Sequence[str]
    title: str
    summary: str
    annotations: Sequence[str]


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
    labels: AbstractSet[str]
    body: str


RED_CONCLUSIONS = frozenset({"failure", "timed_out", "startup_failure"})


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class WindowRun:
    """A workflow run as the red-run analysis reads it.

    Attributes:
        id: its id.
        url: its page.
        conclusion: its conclusion, empty until it completes.
        created_at: when it was created (ISO 8601).
        branch: the branch it ran on.
        head_sha: the commit it ran.
        pulls: the numbers of the PRs GitHub ties it to.
        event: the event that started it.
        updated_at: when it last changed (ISO 8601); its end once completed.
    """

    id: int
    url: str
    conclusion: str
    created_at: str
    branch: str
    head_sha: str
    pulls: Sequence[int]
    event: str
    updated_at: str


class Verdict(enum.Enum):
    """What a review says.

    Attributes:
        APPROVED: the head may merge.
        CHANGES_NEEDED: the head needs changes first.
    """

    APPROVED = enum.auto()
    CHANGES_NEEDED = enum.auto()
