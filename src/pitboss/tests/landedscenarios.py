"""Each shape of write the package makes, with what GitHub holds around it (landed)."""

import dataclasses
from typing import Mapping, Sequence

from .. import actcore, acthub
from .landedhub import GONE

R = "repos/o/r"
FIELDS = {
    "body": "b",
    "title": "t",
    "labels": "a",
    "id": "9",
    "reason": "completed",
    "head": "h",
    "base": "main",
    "name": "p 1",
    "node_id": "N",
    "run": "5",
    "workflow": "check.yml",
    "ref": "main",
    "branch": "w/1",
}
COMMENTS = f"{R}/issues/3/comments?per_page=100&page=1"
SECOND_PAGE = f"{R}/issues/3/comments?per_page=100&page=2"
NEWEST_ISSUE = f"{R}/issues?state=open&sort=created&direction=desc&per_page=1"
NEWEST_PULL = f"{R}/pulls?state=open&sort=created&direction=desc&per_page=1"
LATEST_ISSUES = f"{R}/issues?state=open&sort=created&direction=desc&per_page=30"
PULLS_OF_HEAD = f"{R}/pulls?state=open&head=o%3Ah&per_page=30"
RUNS = f"{R}/actions/workflows/check.yml/runs?event=workflow_dispatch&per_page=1"
PULL = f"{R}/pulls/3"
ISSUE = f"{R}/issues/3"
ONE_COMMENT = f"{R}/issues/comments/9"
ONE_RUN = f"{R}/actions/runs/5"
REF = f"{R}/git/ref/heads/w/1"
QUEUED = {"data": {"node": {"mergeQueueEntry": {"id": "E"}}}}
DEQUEUED = {"data": {"node": {"mergeQueueEntry": None}}}
READ = Mapping[str, object]
CHANGE = actcore.Change(kind="", repo="o/r", number=3, fields=FIELDS)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Scenario:
    """One shape of write.

    Attributes:
        name: what it is.
        words: the ``gh`` line the package builds for it.
        before: what GitHub holds before the write.
        after: what it holds once the write landed.
    """

    name: str
    words: Sequence[str]
    before: READ
    after: READ


def built(kind: str) -> Sequence[str]:
    """The line ``acthub`` builds for a kind of change.

    Args:
        kind: the kind.

    Returns:
        The ``gh`` line.
    """
    return acthub.WRITES[kind](dataclasses.replace(CHANGE, kind=kind))


def of_kind(kind: str, before: READ, after: READ) -> Scenario:
    """The scenario of one of ``acthub``'s kinds.

    Args:
        kind: the kind.
        before: what GitHub holds before.
        after: what it holds after.

    Returns:
        The scenario.
    """
    return Scenario(name=kind, words=built(kind), before=before, after=after)


def single(path: str, before: object, after: object) -> tuple[READ, READ]:
    """What one path holds before and after.

    Args:
        path: the path.
        before: its JSON before.
        after: its JSON after.

    Returns:
        The two states.
    """
    return {path: before}, {path: after}


def held(kind: str, path: str, before: object, after: object) -> Scenario:
    """The scenario of a kind that changes what one path holds.

    Args:
        kind: the kind.
        path: the path.
        before: its JSON before.
        after: its JSON after.

    Returns:
        The scenario.
    """
    return of_kind(kind, *single(path, before, after))


def pr_words(*flags: str) -> Sequence[str]:
    """A ``gh pr merge`` line.

    Args:
        *flags: its flags.

    Returns:
        The line.
    """
    return ["gh", "pr", "merge", "3", "-R", "o/r", *flags]


KINDS = (
    of_kind(
        "comment",
        {COMMENTS: [{"body": "x"}]},
        {COMMENTS: [{"body": "x"}, {"body": "b"}]},
    ),
    held("comment-edit", ONE_COMMENT, {"body": "old"}, {"body": "b"}),
    held("comment-delete", ONE_COMMENT, {"body": "b"}, GONE),
    of_kind(
        "issue",
        {NEWEST_ISSUE: [{"number": 4}], LATEST_ISSUES: [{"number": 4, "title": "t"}]},
        {
            NEWEST_ISSUE: [{"number": 5}],
            LATEST_ISSUES: [{"number": 5, "title": "t"}, {"number": 4, "title": "t"}],
        },
    ),
    of_kind(
        "pr",
        {NEWEST_PULL: [{"number": 4}], PULLS_OF_HEAD: []},
        {NEWEST_PULL: [{"number": 5}], PULLS_OF_HEAD: [{"number": 5}]},
    ),
    held("issue-edit", ISSUE, {"body": "o"}, {"body": "b"}),
    held("close-issue", ISSUE, {"state": "open"}, {"state": "closed"}),
    held("pr-edit", PULL, {"title": "o", "body": "o"}, {"title": "t", "body": "b"}),
    held("pr-close", PULL, {"state": "open"}, {"state": "closed"}),
    held("merge", PULL, {"merged": False}, {"merged": True}),
    held("arm", PULL, {"auto_merge": None}, {"auto_merge": {"by": 1}}),
    held("disarm", PULL, {"auto_merge": {"by": 1}}, {"auto_merge": None}),
    held("undraft", PULL, {"draft": True}, {"draft": False}),
    held("label", ISSUE, {"labels": []}, {"labels": [{"name": "p 1"}]}),
    held("unlabel", ISSUE, {"labels": [{"name": "p 1"}]}, {"labels": []}),
    held("update-branch", PULL, {"head": {"sha": "a"}}, {"head": {"sha": "b"}}),
    held("rerun", ONE_RUN, {"status": "completed"}, {"status": "queued"}),
    held("cancel", ONE_RUN, {"status": "queued"}, {"status": "completed"}),
    held("branch-delete", REF, {"ref": "x"}, GONE),
    held("dequeue", "graphql", QUEUED, DEQUEUED),
    held(
        "dispatch", RUNS, {"workflow_runs": [{"id": 1}]}, {"workflow_runs": [{"id": 2}]}
    ),
)
BY_HAND = (
    Scenario(
        name="gh pr merge",
        words=pr_words("--merge"),
        before={PULL: {"merged": False}},
        after={PULL: {"merged": True}},
    ),
)
ALL = (*KINDS, *BY_HAND)
