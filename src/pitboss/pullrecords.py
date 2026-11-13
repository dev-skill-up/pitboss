"""The typed state a PR's JSON is parsed into (plan section 6.1, keyword: one-path).

``pullobject`` and ``pullstate`` fill these records, once; the gate rows read them.
"""

import dataclasses
from typing import AbstractSet, Mapping, Sequence


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Unread:
    """A fact that was not read.

    Attributes:
        why: GitHub's error, or what was there instead.
    """

    why: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Mistyped:
    """A field of another type than documented, or a required one absent.

    Attributes:
        name: the field.
        said: its value as text, or ``absent``.
    """

    name: str
    said: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Where:
    """Which PR this is and whose.

    Attributes:
        number: the PR's number.
        url: its API URL.
        links: the other URL fields, each None when null.
        base_ref: the base branch.
        base_repo: the base's repository.
        head_sha: the head commit.
        head_repo: the head's repository.
        author: the author's login.
        association: the author's association.
    """

    number: int
    url: str
    links: Mapping[str, str | None]
    base_ref: str
    base_repo: str
    head_sha: str
    head_repo: str
    author: str
    association: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Closure:
    """Whether the PR is still open to change.

    Attributes:
        state: open or closed.
        closed_at: when it closed, if it did.
        merged_at: when it merged, if it did.
        merged_by: who merged it, if anyone.
        merged: whether it merged.
        locked: whether its conversation is locked.
        lock_reason: why, if it is.
    """

    state: str
    closed_at: str | None
    merged_at: str | None
    merged_by: str | None
    merged: bool
    locked: bool
    lock_reason: str | None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Merging:
    """What GitHub says of merging it.

    Attributes:
        draft: whether it is a draft.
        mergeable: GitHub's answer; None while it computes.
        mergeable_state: clean, blocked, behind, dirty and the rest.
        auto_merge: whether auto-merge is armed.
        labels: the label names.
        reviewers: how many reviewers are requested.
        teams: how many teams are requested.
    """

    draft: bool
    mergeable: bool | None
    mergeable_state: str
    auto_merge: bool
    labels: Sequence[str]
    reviewers: int
    teams: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PullObject:
    """The PR object, typed; a field of another type is read as its empty value.

    Attributes:
        where: which PR and whose.
        closure: whether it is open.
        merging: what GitHub says of merging it.
        title_is_text: whether the title is text.
        body: the body; null is empty.
        said: each field as text, for a stop line.
        breaks: the fields absent or mistyped, in the schema's order.
    """

    where: Where
    closure: Closure
    merging: Merging
    title_is_text: bool
    body: str
    said: Mapping[str, str]
    breaks: Sequence[Mistyped]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Run:
    """A check run of the head.

    Attributes:
        name: the check's name.
        status: queued, in_progress or completed.
        conclusion: its conclusion, ``None`` while running.
        number: its id.
        started_at: when it started.
    """

    name: str
    status: str
    conclusion: str
    number: int
    started_at: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Status:
    """A commit status of the head.

    Attributes:
        context: its name.
        state: success, pending, failure or error.
    """

    context: str
    state: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class File:
    """A file the PR changes.

    Attributes:
        name: its path.
        additions: the lines added.
        deletions: the lines deleted.
    """

    name: str
    additions: int
    deletions: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    """A timeline event.

    Attributes:
        kind: the event (commented, reviewed, labeled, ...).
        state: a review's state.
        login: its author or actor.
        body: its text.
        label: a label event's label.
    """

    kind: str
    state: str
    login: str
    body: str
    label: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ticket:
    """An issue the body closes.

    Attributes:
        state: open or closed.
        reason: why it closed, as text.
        locked: whether it is locked.
        is_pull: whether it is a PR, not an issue.
        body: its body, for the review's digest.
    """

    state: str
    reason: str
    locked: bool
    is_pull: bool
    body: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Hold:
    """An open ``pitboss-hold`` issue.

    Attributes:
        title: its title, or its number.
        scope: the actions it holds; ``all`` when its body names none.
    """

    title: str
    scope: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Repository:
    """What the repository and the project say.

    Attributes:
        repo: ``owner/name``.
        number: the PR's number, as asked.
        default_branch: the repository's default branch.
        required_checks: the checks its rules require.
        merge_queue: whether its rules have a merge queue.
        identity: the login the act verbs post with.
        authors: the logins whose PRs are the project's.
        max_lines: the repository's limit of changed lines.
    """

    repo: str
    number: int
    default_branch: str
    required_checks: AbstractSet[str]
    merge_queue: bool
    identity: str
    authors: AbstractSet[str]
    max_lines: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Reads:
    """The lists read of the head and the PR.

    Attributes:
        runs: the head's check runs.
        statuses: the head's statuses.
        files: the files changed.
        timeline: the PR's events, oldest first.
    """

    runs: Sequence[Run] | Unread
    statuses: Sequence[Status] | Unread
    files: Sequence[File] | Unread
    timeline: Sequence[Event] | Unread


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class GateState:
    """What a PR at the merge or the undraft step is gated on, typed.

    Attributes:
        pull: the PR object.
        repository: what the repository and the project say.
        reads: the lists read.
        tickets: each ticket the body closes.
        blockers: the state of each item a Blocked-by line names.
        holds: the repository's holds.
        absent: each input that was not given at all.
    """

    pull: PullObject
    repository: Repository
    reads: Reads
    tickets: Mapping[str, Ticket | Unread]
    blockers: Mapping[str, str]
    holds: Sequence[Hold]
    absent: Sequence[str]
