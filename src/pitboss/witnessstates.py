"""The recorded PRs the witnesses are made of, from the package's own constructors.

pitboss#526 (keyword: progress, witnesses). A witness is a PR the shipped decider
gives a worker task, so the states are made here, in the package, and not by the
tests' fixtures: a proof of the package may not import the tests (a cycle of the
package with them). Each is a ``PullState`` the reader's own parser and the
flow's own record give.
"""

import dataclasses
import json
from typing import AbstractSet, Mapping, Sequence

from . import blankrecords, draftfacts, flowstate, handbacks, headnamed, parsing
from . import shapes, witnessplan
from .headlinepattern import HEAD_LINE

REPOSITORY = "o/r"
HEAD = "a" * 40
OLDER = "b" * 40
BODY = "Fixes #7\n\n## Plan\nthe plan\n\n## Execution\nthe work\n"
CHANGES = shapes.Verdict.CHANGES_NEEDED
APPROVED = shapes.Verdict.APPROVED
PLAN_REJECTED = (CHANGES, None)
EXECUTION_REJECTED = (APPROVED, CHANGES)
GRADED = blankrecords.GRADED
CHECK_RUN = blankrecords.CHECK_RUN
COMMENT = blankrecords.COMMENT
member_comment = blankrecords.member_comment
with_head_line = headnamed.with_head_line
digest = witnessplan.digest
clean_text = witnessplan.clean_text
GREEN = dataclasses.replace(CHECK_RUN, id=1, name="build", finished=True)
RED = dataclasses.replace(CHECK_RUN, id=2, name="test", finished=True, failed=True)


def named_head(body: str, head: str) -> str:
    """A body whose last ``Head:`` line names a head.

    Args:
        body: the body.
        head: the head.

    Returns:
        The body.
    """
    line = f"Head: {head}"
    found = HEAD_LINE.search(body)
    return HEAD_LINE.sub(line, body) if found else f"{body}\n{line}\n"


def pull_json(**changes: object) -> Mapping[str, object]:
    """A PR's JSON as the API gives it, with a Plan and an Execution in its body.

    Args:
        **changes: changes to its JSON.

    Returns:
        The JSON, its body naming the head.
    """
    given: dict[str, object] = {
        "number": 1,
        "title": "PR 1",
        "created_at": "2026-10-01T00:00:00+00:00",
        "draft": False,
        "user": {"login": "pitboss-bot"},
        "body": BODY,
        "head": {"sha": HEAD, "ref": "branch-1"},
        "base": {"ref": "main"},
        "mergeable_state": "clean",
        "auto_merge": None,
        "state": "open",
        "merged_at": None,
        **changes,
    }
    head = given["head"]
    sha = head["sha"] if isinstance(head, dict) else HEAD
    given["body"] = with_head_line(str(given["body"]), str(sha))
    return given


def pull_of(**changes: object) -> shapes.Pull:
    """A PR as the API gives it, with a Plan and an Execution in its body.

    Args:
        **changes: changes to its JSON.

    Returns:
        The PR.
    """
    return parsing.pull(json.dumps(pull_json(**changes)))


def bare(pull: shapes.Pull) -> flowstate.PullState:
    """The state of a PR with no label, check, review or comment.

    Args:
        pull: the PR.

    Returns:
        The state, trusting members, with no draft question.
    """
    return flowstate.PullState(
        pull=pull,
        labels=frozenset(),
        checks=(),
        graded=(),
        comments=(),
        trusted=frozenset({"MEMBER"}),
        undraft_clear=False,
        relock=False,
        draft=draftfacts.NONE,
        recorded=flowstate.Recorded(
            unchanged=frozenset(), handed=handbacks.NOT_REQUIRED
        ),
    )


def with_recorded(
    pr: flowstate.PullState,
    *,
    unchanged: AbstractSet[str] | None = None,
    handed: handbacks.HandedBack | None = None,
) -> flowstate.PullState:
    """A PR with some of what the caller read of the base and the worktree.

    Args:
        pr: the PR.
        unchanged: the reviewed heads since which no code moved; kept when None.
        handed: what the worktree recorded; kept when None.

    Returns:
        The PR with that recorded.
    """
    was = pr.recorded
    recorded = flowstate.Recorded(
        unchanged=was.unchanged if unchanged is None else unchanged,
        handed=was.handed if handed is None else handed,
    )
    return dataclasses.replace(pr, recorded=recorded)


def with_handed(
    pr: flowstate.PullState, handed: handbacks.HandedBack
) -> flowstate.PullState:
    """A PR with what the worktree recorded of its hand-backs.

    Args:
        pr: the PR.
        handed: what the worktree recorded.

    Returns:
        The PR with that recorded.
    """
    recorded = dataclasses.replace(pr.recorded, handed=handed)
    return dataclasses.replace(pr, recorded=recorded)


def graded(
    plan: shapes.Verdict | None,
    execution: shapes.Verdict | None,
    second: int,
    sha: str = HEAD,
) -> shapes.Graded:
    """A regular review as the flow reads it.

    Args:
        plan: its plan grade, None for no ``Plan:`` line.
        execution: its execution grade, None for a review of the plan alone.
        second: the second of the minute it was written.
        sha: the head it reviewed.

    Returns:
        The review.
    """
    when = f"2026-10-30T00:00:{second:02d}Z"
    return dataclasses.replace(
        GRADED, sha=sha, when=when, plan=plan, execution=execution
    )


FIRST_REJECTION = graded(*PLAN_REJECTED, 1, sha=OLDER)
SECOND_REJECTION = graded(*PLAN_REJECTED, 2)


def ruling(second: int, line: str = "Ruling: do these steps") -> shapes.Comment:
    """A recorded Opus ruling.

    Args:
        second: the second of the minute it was written.
        line: its second line.

    Returns:
        The comment.
    """
    return member_comment(
        f"Opus ruling\n{line}\n",
        f"2026-10-30T00:00:{second:02d}Z",
        f"https://example.org/ruling/{second}",
    )


def state(
    *recorded: shapes.Graded,
    comments: Sequence[shapes.Comment] = (),
    checks: Sequence[shapes.CheckRun] = (GREEN,),
    **changes: object,
) -> flowstate.PullState:
    """The recorded data of one PR, whose Plan has a clean ``plan-check``.

    Args:
        *recorded: the reviews that count.
        comments: its issue comments.
        checks: the check runs of its head.
        **changes: changes to the PR's JSON.

    Returns:
        The state.
    """
    pull = pull_of(**changes)
    plan_check = member_comment(clean_text(pull.body), "2026-10-29T00:00:00Z")
    return dataclasses.replace(
        bare(pull),
        checks=checks,
        graded=recorded,
        comments=[*comments, plan_check],
    )
