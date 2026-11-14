"""A gate's typed state made by hand, for the row tests (plan 6.1, keyword: gate).

The rows read only the typed state ``pullstate`` makes; a row test builds that state
here, with no JSON, and changes one value of it.
"""

import dataclasses

from .. import parsing, totalreview
from .. import pullrecords as records

REPO = "example-org/example"
HEAD = "a" * 40
BODY = f"Fixes #1\n\nHead: {HEAD}\n"
# a review attempt; the row tests' policy reads every attempt as an approval
REVIEW = records.Event(
    kind="commented", state="", login="reviewer", body="Verdict: approved", label=""
)
GREEN_RUN = parsing.one_check(
    {
        "name": "check",
        "status": "completed",
        "conclusion": "success",
        "id": 1,
        "started_at": "2026-11-01",
    }
)
OPEN = records.Closure(
    state="open",
    closed_at=None,
    merged_at=None,
    merged_by=None,
    merged=False,
    locked=False,
    lock_reason=None,
)
REPOSITORY = records.Repository(
    repo=REPO,
    number=7,
    default_branch="main",
    required_checks=frozenset({"check"}),
    merge_queue=False,
    identity="agent",
    authors=frozenset({"agent"}),
    max_lines=100,
)


def place_of(**changes: object) -> records.Where:
    """Which PR: number 7 of ``REPO``, from its own branch, by a member.

    Args:
        **changes: the fields to change.

    Returns:
        The PR's place.
    """
    made = records.Where(
        number=7,
        url=f"https://api.github.com/repos/{REPO}/pulls/7",
        links={},
        base_ref="main",
        base_repo=REPO,
        head_sha=HEAD,
        head_ref="work",
        head_repo=REPO,
        author="agent",
        association="MEMBER",
    )
    return dataclasses.replace(made, **changes)  # type: ignore[arg-type]


def merge_fields(**changes: object) -> records.Merging:
    """A PR GitHub says merges: clean, no draft, no label, no review asked.

    Args:
        **changes: the fields to change.

    Returns:
        Its merge fields.
    """
    made = records.Merging(
        draft=False,
        mergeable=True,
        mergeable_state="clean",
        auto_merge=False,
        labels=[],
        reviewers=0,
        teams=0,
    )
    return dataclasses.replace(made, **changes)  # type: ignore[arg-type]


def pull_of(**changes: object) -> records.PullObject:
    """An open PR with a body that closes ticket 1 and names the head.

    Args:
        **changes: the fields to change.

    Returns:
        The PR.
    """
    made = records.PullObject(
        where=place_of(),
        closure=OPEN,
        merging=merge_fields(),
        title_is_text=True,
        body_is_text=True,
        body=BODY,
        said={"title": "the change"},
        breaks=[],
    )
    return dataclasses.replace(made, **changes)  # type: ignore[arg-type]


def lists_of(**changes: object) -> records.Reads:
    """A green head: a check passed, a status passed, a small file, a review.

    Args:
        **changes: the lists to change.

    Returns:
        The reads.
    """
    made = records.Reads(
        runs=[GREEN_RUN],
        statuses=[records.Status(context="text-lint", state="success")],
        files=[records.File(name="src/a.py", additions=3, deletions=1)],
        timeline=[REVIEW],
    )
    return dataclasses.replace(made, **changes)  # type: ignore[arg-type]


def state(**changes: object) -> records.GateState:
    """A reviewed PR nothing stops but its missing ticket, every input read.

    Args:
        **changes: the parts to change.

    Returns:
        The typed state.
    """
    made = records.GateState(
        pull=pull_of(),
        repository=REPOSITORY,
        reads=lists_of(),
        tickets={},
        blockers={},
        holds=[],
        absent=[],
        attempts=[],
    )
    given = dataclasses.replace(made, **changes)  # type: ignore[arg-type]
    timeline = records.listed(given.reads.timeline)
    return dataclasses.replace(given, attempts=totalreview.review_attempts(timeline))


def happened(kind: str, **changes: object) -> records.Event:
    """A timeline event of one kind, by the agent.

    Args:
        kind: the event.
        **changes: the fields to change.

    Returns:
        The event.
    """
    made = records.Event(kind=kind, state="", login="agent", body="", label="")
    return dataclasses.replace(made, **changes)  # type: ignore[arg-type]
