"""The events of the alphabet over the model of a PR (pitboss#444, keyword: properties).

Each event takes a ``model.Model`` to the one it leaves; ``moves`` lists every
event the rules allow, ``simulated`` does the step the flow printed as it says.
"""

import dataclasses
from typing import Callable, Mapping, Sequence, TypedDict, Unpack

from .. import rulingguard, steps
from . import model as modeled
from .model import Allowed, History, Model, Review, Ruling, Verdict, pull_state

Move = Callable[[Model], Model]


class Changes(TypedDict, total=False):
    """The fields of a model an event changes.

    Attributes:
        head: the head's number.
        pushed: when it was pushed.
        ci: the CI state.
        conflict: whether the PR conflicts.
        paused: whether it carries the pause label.
        plan: the Plan's version.
        history: what was posted.
        since_pause: rulings since the last pause.
    """

    head: int
    pushed: int
    ci: str
    conflict: bool
    paused: bool
    plan: int
    history: History
    since_pause: int


class Records(TypedDict, total=False):
    """The lists of a history an event changes.

    Attributes:
        reviews: the reviews.
        rulings: the rulings.
        checks: the Plan checks.
    """

    reviews: Sequence[Review]
    rulings: Sequence[tuple[int, Ruling]]
    checks: Sequence[tuple[int, int, int]]


def _then(model: Model, name: str, **changes: Unpack[Changes]) -> Model:
    return dataclasses.replace(model, last=name, clock=model.clock + 1, **changes)


def _recorded(model: Model, **changes: Unpack[Records]) -> History:
    return dataclasses.replace(model.history, **changes)


def _review(
    model: Model, name: str, plan: Verdict | None, execution: Verdict | None
) -> Model:
    each = (model.clock, plan, execution, model.head, model.plan)
    made = _recorded(model, reviews=[*model.history.reviews, each])
    return _then(model, name, history=made)


def _reviewing(name: str, plan: Verdict | None, execution: Verdict | None) -> Move:
    return lambda model: _review(model, name, plan, execution)


def _checked(model: Model, plan: int, head: int) -> History:
    check = (model.clock, plan, head)
    return _recorded(model, checks=[*model.history.checks, check])


def _pushed(model: Model, name: str) -> Model:
    return _then(model, name, head=model.head + 1, pushed=model.clock, ci="running")


def _push_checked(model: Model, name: str) -> Model:
    pushed = _pushed(model, name)
    return dataclasses.replace(pushed, history=_checked(model, model.plan, pushed.head))


def guard_allows(model: Model) -> bool:
    """Whether the shipped ``rulingguard.refusal`` lets a ruling be posted.

    Args:
        model: the PR.

    Returns:
        True when the guard has no reason to refuse: no ruling is on the PR, or
        it carries the pause label.
    """
    state = pull_state(model)
    texts = [each.body for each in state.comments]
    return rulingguard.refusal(texts, sorted(state.labels)) == ""


def ruled(model: Model, word: Ruling, allowed: Allowed) -> Model | None:
    """A ruling posted, when the rule lets it.

    Args:
        model: the PR.
        word: what it rules.
        allowed: the rule for a ruling (``guard_allows``).

    Returns:
        The model with the ruling, None when the rule refuses it.
    """
    if not allowed(model):
        return None
    made = _recorded(model, rulings=[*model.history.rulings, (model.clock, word)])
    count = model.since_pause + (not model.paused)
    return _then(model, "ruling " + word.value, history=made, since_pause=count)


def paused(model: Model) -> Model:
    """The PR labelled for the owner.

    Args:
        model: the PR.

    Returns:
        The model with the label, and the count of rulings since the pause 0.
    """
    return _then(model, "label", paused=True, since_pause=0)


def _merged(model: Model) -> Model:
    return dataclasses.replace(_pushed(model, "merge of main"), conflict=False)


def _plain() -> Mapping[str, Move]:
    verdicts = {
        "plan review": (Verdict.APPROVED, None),
        "execution review rejects": (Verdict.APPROVED, Verdict.CHANGES_NEEDED),
        "review approves": (Verdict.APPROVED, Verdict.APPROVED),
        "plan rejected": (Verdict.CHANGES_NEEDED, None),
    }
    reviews = {name: _reviewing(name, *grades) for name, grades in verdicts.items()}
    return {
        **reviews,
        "plan check at a new head": lambda m: _push_checked(m, "plan check"),
        "push": lambda m: _pushed(m, "push"),
        "merge of main": _merged,
        "ci green": lambda m: _then(m, "ci green", ci="green"),
        "ci red": lambda m: _then(m, "ci red", ci="red"),
        "label": paused,
        "conflict": lambda m: _then(m, "conflict", conflict=True),
    }


RULINGS = (Ruling.DO_THESE_STEPS, Ruling.REVISE_THE_PLAN, Ruling.ESCALATE)


def moves(model: Model, allowed: Allowed = guard_allows) -> Sequence[Model]:
    """Every model one event of the alphabet leads to.

    Args:
        model: the PR.
        allowed: the rule for a ruling.

    Returns:
        The models; an event the rules refuse (a second ruling) leads nowhere.
    """
    found: list[Model | None] = [each(model) for each in _plain().values()]
    found += [ruled(model, word, allowed) for word in RULINGS]
    return list(filter(None, found))


def _reviewed(model: Model, step: steps.Next) -> Model:
    grades: Mapping[steps.Stage | None, Verdict | None] = {steps.Stage.PLAN_ONLY: None}
    chosen = grades.get(step.stage, Verdict.APPROVED)
    return _review(model, "review", Verdict.APPROVED, chosen)


def _worked(model: Model, step: steps.Next) -> Model:
    task = step.task
    if task is steps.Task.RESOLVE_CONFLICT:
        return dataclasses.replace(_pushed(model, "worker"), conflict=False, ci="green")
    if task is steps.Task.FIX_CI:
        return dataclasses.replace(_pushed(model, "worker"), ci="green")
    done = dataclasses.replace(_push_checked(model, "worker"), ci="green")
    if task is not steps.Task.REVISE_PLAN:
        return done
    made = _checked(model, model.plan + 1, done.head)
    return dataclasses.replace(done, plan=model.plan + 1, history=made)


def simulated(model: Model, step: steps.Move, allowed: Allowed) -> Model | None:
    """The model after the step is done as it says.

    Args:
        model: the PR.
        step: the step printed for it.
        allowed: the rule for a ruling.

    Returns:
        The model, None for a step that waits for the owner or ends the PR.
    """
    if modeled.ci_waits(model, step):
        return _then(model, "ci green", ci="green")
    if not isinstance(step, steps.Next):
        return None
    made = _checked(model, model.plan, model.head)
    done: Mapping[steps.Step, Callable[[], Model | None]] = {
        steps.Step.OPUS_RULING: lambda: ruled(model, Ruling.DO_THESE_STEPS, allowed),
        steps.Step.PAUSE_FOR_OWNER: lambda: paused(model),
        steps.Step.PLAN_CHECK: lambda: _then(model, "plan check", history=made),
        steps.Step.SEND_BACK_PLAN_CHECK: lambda: _push_checked(model, "send back"),
        steps.Step.REGULAR_REVIEW: lambda: _reviewed(model, step),
        steps.Step.WORKER: lambda: _worked(model, step),
    }
    return done[step.step]() if step.step in done else None
