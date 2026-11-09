"""The world of a rejected Execution whose fix round has not run (pitboss#390).

Keyword: unfixed-execution. PR 3 had its Execution rejected at an older head, an
Opus ruling followed, and a Plan revision ended with an empty commit, so the
head carries no code the rejection has not seen; the Plan alone was approved at
that head.
"""

from .. import shapes
from . import test_flow, test_flow_sweep as flows, world

REJECTED = flows.graded(flows.APPROVED, flows.CHANGES, 1, sha=flows.OLDER)
PLAN_APPROVED = flows.graded(flows.APPROVED, None, 3)


def ruling(word: str = "revise the plan") -> shapes.Comment:
    """The Opus ruling between the rejection and the approval.

    Args:
        word: what it rules.

    Returns:
        The comment.
    """
    return test_flow.ruling(2, line=f"Ruling: {word}")


def rounds(*recorded: shapes.Comment) -> world.World:
    """A world whose head moved from the rejected one by an empty commit.

    Args:
        *recorded: PR 3's comments.

    Returns:
        The world.
    """
    here = flows.world_with(recorded)
    here.bodies[f"{world.PROJECT}/commits/2"] = {"files": []}
    return here


def after_the_ruling() -> world.World:
    """The Execution rejected, ruled on, the Plan revised and approved alone.

    Returns:
        The world.
    """
    return rounds(REJECTED, ruling(), PLAN_APPROVED)
