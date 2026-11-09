"""The step before a Plan review (keyword: plan-check, pitboss#192).

A Plan with commands is offered for its review only after a trusted comment
records a clean ``pitboss plan-check`` of this Plan: the commands were run, and
each of them ran as written. A Plan with no command needs no check.
"""

from typing import AbstractSet, Protocol, Sequence

from . import bodydigest, expansion, plandigest, planbody, sessionurl, shapes, steps


def is_plan_check(body: str, digest: str) -> bool:
    """Whether a comment is a clean ``plan-check`` of the Plan with a digest.

    Args:
        body: the comment.
        digest: the digest of the Plan section.

    Returns:
        True when its first line is ``Plan check``, it has the line
        ``Plan check: ok`` and it records that Plan digest.
    """
    lines = [each.rstrip() for each in sessionurl.lines(body)]
    return (
        bool(lines)
        and lines[0] == steps.PLAN_CHECK_FIRST_LINE
        and steps.PLAN_CHECK_OK in lines
        and bodydigest.recorded_after(body, bodydigest.PLAN_PREFIX) == digest
    )


def needs_check(
    body: str, comments: Sequence[shapes.Comment], trusted: AbstractSet[str]
) -> bool:
    """Whether the Plan has commands and no trusted comment checked this Plan.

    Args:
        body: the PR body.
        comments: the PR's issue comments.
        trusted: the author associations whose comments count.

    Returns:
        True when a Plan review must wait for the check. A directive with no
        command is a Plan that needs it too (the check refuses it).
    """
    section = plandigest.section(body)
    try:
        rows = expansion.commands(section)
    except expansion.TemplateError:
        rows = ["a directive with no command"]
    # keyword: plan-digest-collapse (pitboss#358, #399): a check that recorded the
    # digest of before the expanded blocks were collapsed still counts
    digests = expansion.accepted_digests(section)
    return bool(rows) and not any(
        is_plan_check(each.body, digest)
        for each in comments
        if each.author_association in trusted
        for digest in digests
    )


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


def review(pr: Described, stage: steps.Stage) -> steps.Next:
    """A review that grades the Plan, once the Plan's commands were checked.

    Args:
        pr: the PR.
        stage: what the review grades.

    Returns:
        The check step while the Plan has commands no clean check covers, else
        the review.
    """
    if needs_check(pr.pull.body, pr.comments, pr.trusted):
        return steps.plan_check()
    return steps.regular_review(stage)


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
        return steps.worker(steps.Task.RUN_PLAN)
    if planbody.ci_quotes_missing(pr.pull.body):
        return steps.worker(steps.Task.ADD_CI_QUOTES)
    return steps.regular_review(stage)
