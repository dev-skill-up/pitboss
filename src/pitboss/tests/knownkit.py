"""What the 66 cases run on: the controls, each of which a removal can take out.

A case passes only when its control refuses the unsafe world and lets its safe
twin through, so a control that refuses everything does not pass. ``Kit`` holds
every control a case runs; ``knownremovals`` takes one out at a time.
"""

import dataclasses
import pathlib
from typing import Callable, Mapping, Sequence

from .. import (
    actcore,
    actverbs,
    dispatchnext,
    handbackform,
    nolocalmutants,
    rulecases,
    rulecount,
    rulefiles,
    ticketreader,
    totalroutes,
    totalverdict,
)
from ..totaljson import JsonMap
from . import fakehub, knowngit, scratch, totalworld
from .totalworld import World

REFUSALS = (
    actcore.Refused,
    rulefiles.Refused,
    ticketreader.Refused,
    dispatchnext.Refused,
    rulecases.Refused,
)
Brief = Callable[[rulefiles.Ticket], str]
Recount = Callable[[str, rulefiles.Ticket], Sequence[str]]
Add = Callable[
    [Sequence[rulecases.Case], rulecases.Case, Mapping[str, rulecases.Encoding]], str
]
Diff = Callable[
    [Sequence[rulecases.Case], Sequence[rulecases.Case], Mapping[str, str]],
    Sequence[str],
]
Findings = Callable[[str, Sequence[str], handbackform.Exists], Sequence[str]]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Kit:
    """The controls the cases run.

    Attributes:
        policy: the verdict's rows.
        controls: the act verbs' gates and readers.
        verbs: the act verbs.
        requirements: the instructions' text.
        brief: the brief writer.
        recount: the brief's recount.
        add: the recording of a ruling as a case.
        diff_findings: the check of a change of the cases.
        findings: the hand-back form.
        registrations: the check that no command runs mutants.
    """

    policy: totalverdict.Policy
    controls: actcore.Controls
    verbs: Mapping[str, actverbs.Verb] = dataclasses.field(
        default_factory=lambda: actverbs.VERBS
    )
    requirements: Mapping[str, Sequence[str]] = dataclasses.field(
        default_factory=lambda: totalroutes.REQUIREMENTS
    )
    brief: Brief = rulefiles.write
    recount: Recount = rulecount.missing
    add: Add = rulecases.add
    diff_findings: Diff = rulecases.diff_findings
    findings: Findings = handbackform.findings
    registrations: Callable[[pathlib.Path], Sequence[str]] = (
        nolocalmutants.registrations
    )


def kit() -> Kit:
    """Every control as pitboss ships it.

    Returns:
        The kit.
    """
    policy = totalverdict.shipped_policy()
    return Kit(policy=policy, controls=controls_of(policy))


def controls_of(policy: totalverdict.Policy, **changes: object) -> actcore.Controls:
    """The act verbs' controls over a policy.

    Args:
        policy: the verdict's rows.
        **changes: other controls to set.

    Returns:
        The controls.
    """
    made = actcore.Controls(
        verdict=lambda action, pull, ctx: totalverdict.verdict(
            action, pull, ctx, policy
        ),
        not_overridable=policy.not_overridable,
    )
    return dataclasses.replace(made, **changes)  # type: ignore[arg-type]


BASE = totalworld.base()
REPO = str(BASE.ctx["repo"])
NUMBER = int(str(BASE.pull["number"]))
HEAD = totalworld.head_of(BASE)
BODY = str(BASE.pull["body"])
TARGET = actcore.Target(repo=REPO, number=NUMBER)
OK_PREPUSH = (0, "lint passed\nok\n")


def verdict(given: Kit, action: str, world: World) -> totalverdict.Answer:
    """The verdict on a world, with the kit's rows.

    Args:
        given: the kit.
        action: the action.
        world: the world.

    Returns:
        The answer.
    """
    return given.controls.verdict(action, world.pull, world.ctx)


def stops(given: Kit, action: str, world: World, row: str) -> bool:
    """Whether the verdict stops on a row.

    Args:
        given: the kit.
        action: the action.
        world: the world.
        row: the start of the line.

    Returns:
        True when it is STOP with a line that starts with the row.
    """
    answer = verdict(given, action, world)
    return answer.word == totalverdict.STOP and any(
        each.startswith(row) for each in answer.lines
    )


def goes(given: Kit, action: str, world: World) -> bool:
    """Whether the verdict is GO.

    Args:
        given: the kit.
        action: the action.
        world: the world.

    Returns:
        True for GO.
    """
    return verdict(given, action, world).word == totalverdict.GO


def change(
    pull: JsonMap | None = None,
    ctx: JsonMap | None = None,
    events: Sequence[object] = (),
) -> World:
    """The GO world with inputs changed.

    Args:
        pull: PR fields to set.
        ctx: inputs to set.
        events: timeline events to add.

    Returns:
        The world.
    """
    return totalworld.change(BASE, pull, ctx, events)


def draft(ctx: JsonMap | None = None) -> World:
    """The GO world as a draft.

    Args:
        ctx: inputs to set.

    Returns:
        The world.
    """
    return totalworld.change(BASE, {"draft": True}, ctx)


def review_with(edit: Callable[[str], str]) -> object:
    """The GO world's review with its text changed.

    Args:
        edit: the change of the text.

    Returns:
        The review event.
    """
    made = totalworld.review(HEAD, BODY, dict(BASE.ctx["tickets"]))  # type: ignore[call-overload]
    return {**made, "body": edit(str(made["body"]))}


def made(
    given: Kit, world: World = BASE, owner: actcore.Owner | None = None
) -> fakehub.Made:
    """A fake GitHub holding a world, with the kit's controls.

    Args:
        given: the kit.
        world: the world.
        owner: the owner's messages.

    Returns:
        The hub and the verb's world.
    """
    return fakehub.made(world, given.controls, owner)


def act(given: Kit, hub: fakehub.Made, verb: str, **options: str) -> str:
    """Run a verb on the world's PR.

    Args:
        given: the kit.
        hub: the hub and the verb's world.
        verb: the verb.
        **options: its options (``_`` for ``-``).

    Returns:
        What it said.
    """
    words = {key.replace("_", "-"): value for key, value in options.items()}
    target = actcore.Target(
        repo=words.pop("repo", REPO), number=int(words.pop("number", str(NUMBER)))
    )
    return given.verbs[verb](hub.act, target, words)


def refused(run: Callable[[], object]) -> str:
    """Whether a call is refused.

    Args:
        run: the call.

    Returns:
        The refusal's text ("refused" when it has none), or "" when it went.
    """
    try:
        run()
    except REFUSALS as error:
        return str(error) or "refused"
    return ""


CHECKOUTS = fakehub.rule_checkouts(scratch.process_directory())


def brief(given: Kit, repo: str, *paths: str) -> tuple[str, rulefiles.Ticket]:
    """The kit's brief for a ticket of a real repository.

    Args:
        given: the kit.
        repo: the repository (``bats``, ``pwa``, ``quire``).
        *paths: the ticket's paths.

    Returns:
        The brief and the ticket it is for.
    """
    found = knowngit.ticket(CHECKOUTS[f"bats-lang/{repo}"], *paths)
    return given.brief(found), found


Case = Callable[[Kit], bool]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Known:
    """One case.

    Attributes:
        control: the control that holds it.
        what: the world that was run.
        run: the case.
    """

    control: str
    what: str
    run: Case


def registry(
    cases: dict[str, Known],
) -> Callable[[str, str, str], Callable[[Case], Case]]:
    """The decorator that registers a case in a module's table.

    Args:
        cases: the module's table, by id.

    Returns:
        ``case(name, control, what)``, the decorator of one case.
    """

    def case(name: str, control: str, what: str) -> Callable[[Case], Case]:
        def register(run: Case) -> Case:
            cases[name] = Known(control=control, what=what, run=run)
            return run

        return register

    return case


def dispatch(
    given: Kit, hub: fakehub.Made, state: dispatchnext.State, **options: str
) -> str:
    """Run ``dispatch-next`` over a state.

    Args:
        given: the kit.
        hub: the hub and the verb's world.
        state: what the order reads.
        **options: ``want`` and ``agent``.

    Returns:
        The item it answers.
    """
    world = dataclasses.replace(hub.act, work=lambda: state)
    return given.verbs["dispatch-next"](world, actcore.Target(repo=REPO), options)


def pushed(
    given: Kit, worktree: pathlib.Path, prepush: tuple[int, str] = (0, "ok\n")
) -> str:
    """Run ``push`` of a worktree to ``worker/7``.

    Args:
        given: the kit.
        worktree: the worktree.
        prepush: what the pre-push check says.

    Returns:
        What it said.
    """
    hub = made(given)
    world = dataclasses.replace(hub.act, prepush=lambda: prepush)
    options = {"worktree": str(worktree), "branch": "worker/7"}
    return given.verbs["push"](world, actcore.Target(repo=REPO), options)
