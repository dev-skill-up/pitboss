"""The parts of GitHub's REST responses that pitboss reads, as dataclasses.

``parsing`` builds them from response bodies, so nothing else touches JSON.
"""

import dataclasses
import enum
from typing import AbstractSet, Sequence

WAITING_STATUSES = frozenset({"queued"})


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
        repo: the ``owner/name`` of the repository it lives in ("" when
            GitHub does not say, as for a deleted fork).
    """

    sha: str
    branch: str
    repo: str


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
        merged_at: when it merged (ISO 8601), or empty.
    """

    branch: str
    still_open: bool
    merged: bool
    merged_at: str = ""


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
        run: the id of its Actions workflow run (0 when not an Actions check).
        succeeded: whether it completed with the conclusion ``success``.
        said: its status and conclusion as GitHub wrote them (keyword: gate).
    """

    id: int
    name: str
    finished: bool
    failed: bool
    head_sha: str
    started_at: str
    completed_at: str
    run: int
    succeeded: bool
    said: tuple[str, str]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class CommitStatus:
    """The newest commit status of one context on a commit.

    Attributes:
        context: its context (``text-lint``).
        succeeded: whether its state is ``success``.
        created_at: when it was posted (ISO 8601).
        run: the id of the Actions run its target URL names (0 when none).
        state: its state (``failure``, ``pending``, ...), empty when not known.
        description: the text the poster gave it, empty when none.
        url: its target URL, empty when none.
    """

    context: str
    succeeded: bool
    created_at: str
    run: int
    state: str
    description: str
    url: str


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
        url: its address (``html_url``), empty when the API gave none.
        login: its author's login (the gate reads ``act``'s records by it).
    """

    body: str
    author_association: str
    created_at: str
    url: str
    login: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PullReview:
    """A GitHub pull request review.

    Attributes:
        state: ``APPROVED``, ``CHANGES_REQUESTED``, ``COMMENTED``, ...
        commit_id: the commit it reviewed.
        author_association: its author's relation to the repository.
        submitted_at: when it was submitted (ISO 8601).
        body: its text (the gate reads a review attempt in it).
        login: its author's login.
    """

    state: str
    commit_id: str
    author_association: str
    submitted_at: str
    body: str
    login: str


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
class TimelineEvent:
    """One event of a PR's timeline.

    Attributes:
        kind: GitHub's event name (``added_to_merge_queue``).
        at: when it happened (ISO 8601), empty for an event with no time.
    """

    kind: str
    at: str


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
        comments: how many comments it has.
    """

    number: int
    title: str
    created_at: str
    labels: AbstractSet[str]
    body: str
    comments: int


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


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Unreadable:
    """An open PR one of whose API calls failed.

    Attributes:
        reference: its ``owner/name#number``.
        call: the call that failed (``check-runs``).
        status: how it failed (``HTTP 500``).
    """

    reference: str
    call: str
    status: str


class Standing(enum.Enum):
    """Where a PR's head stands with its newest review.

    Attributes:
        NONE: no review counts.
        APPROVED: approved, this very head.
        APPROVED_BEFORE_MERGES: an older head approved, merges or zips since.
        CHANGES_NEEDED: this very head needs changes.
        OLDER_HEAD: the review is of an older head (a fix came since).
        OLDER_BODY: the review is of this head, but the PR body is not the one
            it recorded (a body fix came since; keyword: body-digest).
        PLAN_CHANGES_NEEDED: this head's plan needs changes (revise it only).
        PLAN_APPROVED: this head's review approved the plan alone (no merge).
    """

    NONE = enum.auto()
    APPROVED = enum.auto()
    APPROVED_BEFORE_MERGES = enum.auto()
    CHANGES_NEEDED = enum.auto()
    OLDER_HEAD = enum.auto()
    OLDER_BODY = enum.auto()
    PLAN_CHANGES_NEEDED = enum.auto()
    PLAN_APPROVED = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Graded:
    """A review as the flow reads it.

    Attributes:
        sha: the head it reviewed (possibly abbreviated).
        when: when it was written (ISO 8601).
        plan: what its ``Plan:`` line grades, None with no such line.
        execution: its verdict, None for a review of the plan alone.
        comment: whether it is a regular review (a comment, not a GitHub review).
        body: the digest of the PR body it records, empty when it records none.
        missed: how many of its findings it marks ``Missed earlier:`` (keyword:
            all-findings).
        plan_digest: the digest of the Plan section it records, empty when it
            records none (keyword: plan-digest).
    """

    sha: str
    when: str
    plan: Verdict | None
    execution: Verdict | None
    comment: bool
    body: str
    missed: int
    plan_digest: str
