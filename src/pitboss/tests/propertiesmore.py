"""Properties P2 and P3 of the review flow (pitboss#444, keyword: properties).

P2: a ``do these steps`` ruling no review or push followed is the step, at every
state. P3: a Plan check at a later head keeps the digest of an approved Plan.
"""

from typing import Callable

from .. import expansion, plandigest, steps
from . import model

Allowed = model.Allowed


RUNNING = ("running",)
RED = ("red",)


def _read(digest: Callable[[str], str], version: int, head: int) -> str:
    # the digest of a version of the Plan as the body reads at a head
    return digest(plandigest.section(model.body_of(version, head)))


def unapplied(at: model.Model) -> bool:
    """Whether the newest ruling says ``do these steps`` and nothing followed it.

    Args:
        at: the PR.

    Returns:
        True when no review and no push is newer than that ruling.
    """
    rulings = at.history.rulings
    when, word = rulings[-1] if rulings else (0, None)
    later = [each for each in at.history.reviews if each[0] > when]
    return word is model.Ruling.DO_THESE_STEPS and not later and at.pushed < when


def _plan_edited(step: steps.Move) -> bool:
    return steps.step_of(step) is steps.Step.PLAN_EDITED


def _held_first(at: model.Model, step: steps.Move) -> bool:
    # the pause, an edited Plan and a running CI come before a ruling's steps
    edited = any(each[4] != at.plan for each in at.history.reviews)
    return (
        (isinstance(step, steps.Idle) and at.paused)
        or (_plan_edited(step) and edited)
        or (model.ci_waits(at, step) and at.ci in RUNNING)
    )


def p2_ruling_steps(at: model.Model, step: steps.Move, allowed: Allowed) -> str:
    """P2: a ``do these steps`` ruling no review or push followed is the step.

    At every state, not after a chosen last event. The only steps that come
    before it are the ones the order of ``flow.ROWS`` puts first, each held by its
    own cause: the pause, an edited Plan, a conflict, a CI that runs or is red.

    Args:
        at: the PR.
        step: its step.
        allowed: the rule for a ruling (unused).

    Returns:
        The finding, empty when the property holds.
    """
    task = steps.task_of(step)
    ruled = task is steps.Task.RULING_STEPS
    fixing = task is steps.Task.RESOLVE_CONFLICT and at.conflict
    fixing = fixing or task is steps.Task.FIX_CI and at.ci in RED
    ahead = _held_first(at, step) or fixing
    return (
        "P2: the ruling's steps are not the step"
        if unapplied(at) and not ruled and not ahead
        else ""
    )


def p3_plan_digest(
    at: model.Model,
    step: steps.Move,
    allowed: Allowed,
    digest: Callable[[str], str] = expansion.section_digest,
) -> str:
    """P3: a Plan check at a later head keeps the digest of an approved Plan.

    Each Plan check and review of the PR was made at a head; the digest of the
    Plan it read, as ``digest`` gives it, is the digest of the same version of the
    Plan at the PR's head now (only the run and job ids of the Actions addresses
    differ), and the flow does not say the Plan was edited when no version differs.

    Args:
        at: the PR.
        step: its step.
        allowed: the rule for a ruling (unused).
        digest: the digest of a Plan section (the one that reads the ids is the
            planted violation).

    Returns:
        The finding, empty when the property holds.
    """
    made = [(version, head) for _, version, head in at.history.checks]
    made += [(each[4], each[3]) for each in at.history.reviews]
    moved = any(_read(digest, v, h) != _read(digest, v, at.head) for v, h in made)
    edited = _plan_edited(step) and all(v == at.plan for v, _ in made)
    return (
        "P3: a later head changed the digest of an approved Plan"
        if moved or edited
        else ""
    )
