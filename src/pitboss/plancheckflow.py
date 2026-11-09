"""The step before a Plan review (keyword: plan-check, pitboss#192).

A Plan with commands is offered for its review only after the newest trusted
comment that records a ``pitboss plan-check`` of this Plan is a clean one: the
commands were run, and each of them ran as written. A Plan with no command needs
no check. A refusal is the fix round, with its findings quoted (keyword:
fix-round-kind, pitboss#390).
"""

import re
from typing import AbstractSet, Protocol, Sequence

from . import bodydigest, expansion, plandigest, planbody, sessionurl, shapes, steps

QUOTED = 600


def records_check(body: str, digest: str) -> bool:
    """Whether a comment is a ``plan-check`` of the Plan with a digest.

    Args:
        body: the comment.
        digest: the digest of the Plan section.

    Returns:
        True when its first line is ``Plan check`` and it records that Plan
        digest, whatever it found.
    """
    lines = sessionurl.lines(body)
    return (
        bool(lines)
        and lines[0].rstrip() == steps.PLAN_CHECK_FIRST_LINE
        and bodydigest.recorded_after(body, bodydigest.PLAN_PREFIX) == digest
    )


def is_plan_check(body: str, digest: str) -> bool:
    """Whether a comment is a clean ``plan-check`` of the Plan with a digest.

    Args:
        body: the comment.
        digest: the digest of the Plan section.

    Returns:
        True when it records that Plan digest and has the line
        ``Plan check: ok``.
    """
    lines = [each.rstrip() for each in sessionurl.lines(body)]
    return records_check(body, digest) and steps.PLAN_CHECK_OK in lines


def newest_check(
    body: str, comments: Sequence[shapes.Comment], trusted: AbstractSet[str]
) -> shapes.Comment | None:
    """The newest trusted comment that records a check of this Plan.

    Args:
        body: the PR body.
        comments: the PR's issue comments.
        trusted: the author associations whose comments count.

    Returns:
        The comment, or None when no trusted comment records a check of the
        Plan section as it is now.
    """
    section = plandigest.section(body)
    # keyword: plan-digest-collapse (pitboss#358, #399): a check that recorded the
    # digest of before the expanded blocks were collapsed still counts
    digests = expansion.accepted_digests(section)
    found = [
        each
        for each in comments
        if each.author_association in trusted
        and any(records_check(each.body, digest) for digest in digests)
    ]
    return max(found, key=lambda each: each.created_at, default=None)


def findings(check: shapes.Comment) -> str:
    """The findings of a ``plan-check`` comment, in one line.

    Args:
        check: the comment.

    Returns:
        Its lines but the first, the rows that ran and the Plan digest, joined
        with ``" | "`` and cut at ``QUOTED`` characters.
    """
    lines = [each.strip() for each in sessionurl.lines(check.body)][1:]
    shown = [
        each
        for each in lines
        if each
        and not each.startswith(bodydigest.PLAN_PREFIX)
        and not re.match(r"row \d+: ran,", each)
    ]
    quoted = " | ".join(shown)
    return quoted if len(quoted) <= QUOTED else quoted[: QUOTED - 3] + "..."


def needs_check(
    body: str, comments: Sequence[shapes.Comment], trusted: AbstractSet[str]
) -> bool:
    """Whether the Plan has commands and its newest recorded check is not clean.

    Args:
        body: the PR body.
        comments: the PR's issue comments.
        trusted: the author associations whose comments count.

    Returns:
        True when a Plan review must wait for the check. A directive with no
        command is a Plan that needs it too (the check refuses it).
    """
    try:
        rows = expansion.commands(plandigest.section(body))
    except expansion.TemplateError:
        rows = ["a directive with no command"]
    newest = newest_check(body, comments, trusted)
    clean = newest is not None and any(
        is_plan_check(newest.body, digest)
        for digest in expansion.accepted_digests(plandigest.section(body))
    )
    return bool(rows) and not clean


def refusal(
    body: str, comments: Sequence[shapes.Comment], trusted: AbstractSet[str]
) -> shapes.Comment | None:
    """The comment of a check that refused the Plan as it is now.

    Args:
        body: the PR body.
        comments: the PR's issue comments.
        trusted: the author associations whose comments count.

    Returns:
        The newest check of this Plan when it is not clean, else None.
    """
    newest = newest_check(body, comments, trusted)
    refused = newest is not None and needs_check(body, comments, trusted)
    return newest if refused else None


class Described(Protocol):
    """What the review of a Plan reads of a PR (``flowstate.PullState``)."""

    @property
    def pull(self) -> shapes.Pull:
        """The PR.

        Returns:
            The value.
        """

    @property
    def comments(self) -> Sequence[shapes.Comment]:
        """Its issue comments.

        Returns:
            The value.
        """

    @property
    def trusted(self) -> AbstractSet[str]:
        """The author associations whose comments count.

        Returns:
            The value.
        """

    @property
    def no_drafts(self) -> bool:
        """Whether its repository has no drafts.

        Returns:
            The value.
        """


def review(pr: Described, stage: steps.Stage) -> steps.Next:
    """A review that grades the Plan, once the Plan's commands were checked.

    Args:
        pr: the PR.
        stage: what the review grades.

    Returns:
        While the Plan has commands no clean check covers: the fix round with
        the findings quoted when the newest check of this Plan refused it, else
        the check step; otherwise the review.
    """
    if needs_check(pr.pull.body, pr.comments, pr.trusted):
        refused = refusal(pr.pull.body, pr.comments, pr.trusted)
        if refused is None:
            return steps.plan_check()
        return steps.fix_round(refused.url, findings(refused))
    return steps.regular_review(stage)


def filled(
    body: str, comments: Sequence[shapes.Comment], trusted: AbstractSet[str]
) -> bool:
    """Whether the Execution is written and the Plan check is clean.

    Args:
        body: the PR body.
        comments: the PR's issue comments.
        trusted: the author associations whose comments count.

    Returns:
        True when no worker has anything to fill: the Execution is neither empty
        nor a placeholder and no Plan command lacks a clean check (keyword:
        filled-execution, pitboss#390).
    """
    unwritten = planbody.execution_unwritten(body)
    return not unwritten and not needs_check(body, comments, trusted)


def write_round(pr: Described) -> steps.Next:
    """The worker round that writes the Execution of a PR.

    Args:
        pr: the PR, whose Execution is empty or a placeholder.

    Returns:
        The round that runs the Plan's commands and fills the Execution; for a
        repository with no drafts, the one that writes the body (keyword:
        no-drafts, pitboss#390).
    """
    task = steps.Task.FIRST_ROUND if pr.no_drafts else steps.Task.RUN_PLAN
    return steps.worker(task)


def execution_review(pr: Described, stage: steps.Stage) -> steps.Next:
    """A review of the Execution, once the Execution is written.

    Args:
        pr: the PR, whose Plan is approved.
        stage: what the review grades.

    Returns:
        The worker round that runs the Plan's commands and fills the Execution
        while the body's Execution section is empty or a placeholder (keyword:
        unwritten-execution, pitboss#294), or the one that adds the CI quotes
        the Plan names (keyword: ci-quotes, pitboss#277), else the review.
    """
    if planbody.execution_unwritten(pr.pull.body):
        return write_round(pr)
    if planbody.ci_quotes_missing(pr.pull.body):
        return steps.worker(steps.Task.ADD_CI_QUOTES)
    return steps.regular_review(stage)
