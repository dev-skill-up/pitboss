"""A run of a head stuck queued, as read, and its line (B22, keyword: stuck-ci).

The reader (``stuckci``) reads the runs and keeps each stuck one as a ``Stuck``;
``decide`` says the owner's step from it with ``warning``, so the line is built
where the decision is (plan 6.1, 3.1(3)).
"""

import dataclasses

from . import rerunrule, shapes

PREFIX = "STUCK CI"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Stuck:
    """A run of a PR's head queued past the limit while later runs completed.

    Attributes:
        slug: the repository, ``owner/name``.
        number: the PR.
        head: the head commit.
        run: the run.
        minutes: how long it has been queued.
        later: how many later runs of the repository completed.
    """

    slug: str
    number: int
    head: str
    run: shapes.WorkflowRun
    minutes: int
    later: int


def warning(found: Stuck) -> str:
    """The ``STUCK CI`` line of one stuck run: the owner's step.

    Args:
        found: the run, as read.

    Returns:
        The line, with the command that lists the runs and the owner's step.
    """
    slug, head = found.slug, found.head
    step = rerunrule.step(rerunrule.Run(status=found.run.status, jobs=0))
    return (
        f"{PREFIX} {slug}#{found.number}: run {found.run.id} queued {found.minutes}"
        f" minutes while {found.later} later runs of the repository completed; list"
        f" them: gh api repos/{slug}/actions/runs?head_sha={head}; the step is the"
        f" owner's: {step}"
    )
