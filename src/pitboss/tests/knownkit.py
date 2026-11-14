"""What the 59 cases run on: the controls, each of which a removal can take out.

A case passes only when its control refuses the unsafe world and lets its safe
twin through, so a control that refuses everything does not pass. ``Kit`` holds
every control a case runs; ``knownremovals`` takes one out at a time.
"""

import dataclasses
import functools
import pathlib
from typing import Callable, Mapping, MutableMapping, Sequence

from .. import (
    actcore,
    actfacts,
    actrules,
    actverbs,
    answer,
    handbackform,
    pullstate,
    nolocalmutants,
    render,
    rulecases,
    rulecount,
    rulefiles,
)
from ..totaljson import JsonMap, members
from . import fakegiven, fakehub, gatewords, knowngit, scratch, totalworld
from .totalworld import World

REFUSALS = (
    actcore.Refused,
    rulefiles.Refused,
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
Verb = Callable[[actcore.Act, actcore.Target, Mapping[str, str]], str]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Kit:
    """The controls the cases run (``knownshipped.shipped`` as pitboss ships them).

    Attributes:
        rests: the gate and the act verbs' controls.
        verbs: the act verbs.
        requirements: the instructions' text.
        brief: the brief writer.
        recount: the brief's recount.
        add: the recording of a ruling as a case.
        diff_findings: the check of a change of the cases.
        findings: the hand-back form.
        registrations: the check that no command runs mutants.
    """

    rests: fakegiven.Given
    verbs: Mapping[str, Verb]
    requirements: Mapping[str, Sequence[str]] = dataclasses.field(
        default_factory=lambda: actrules.REQUIREMENTS
    )
    brief: Brief = rulefiles.write
    recount: Recount = rulecount.missing
    add: Add = rulecases.add
    diff_findings: Diff = rulecases.diff_findings
    findings: Findings = handbackform.findings
    registrations: Callable[[pathlib.Path], Sequence[str]] = (
        nolocalmutants.registrations
    )


BASE = totalworld.base()
REPO = str(BASE.ctx["repo"])
NUMBER = int(str(BASE.pull["number"]))
HEAD = totalworld.head_of(BASE)
BODY = str(BASE.pull["body"])
TARGET = actcore.Target(repo=REPO, number=NUMBER)
OK_PREPUSH = (0, "lint passed\nok\n")


def verdict(given: Kit, action: str, world: World) -> gatewords.Answer:
    """The gate's stops of an action on a world, with the kit's rows.

    Args:
        given: the kit.
        action: the action.
        world: the world.

    Returns:
        The answer.
    """
    rests = given.rests
    gated = pullstate.gate_of(world.pull, world.ctx)
    found = rests.gating(action, gated, rests.policy)
    said = gatewords.STOP if found else gatewords.GO
    return gatewords.Answer(word=said, lines=[each.line for each in found], stops=found)


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
    return answer.word == gatewords.STOP and any(
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
    return verdict(given, action, world).word == gatewords.GO


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
    made = totalworld.review(HEAD, BODY, base_map("ctx", "tickets"))
    return {**made, "body": edit(str(made["body"]))}


def base_map(part: str, key: str) -> MutableMapping[str, object]:
    """A copy of an object of the GO world.

    Args:
        part: ``pull`` or ``ctx``.
        key: the key in it.

    Returns:
        The object's members.
    """
    return dict(members(getattr(BASE, part).get(key)))


def base_items(key: str) -> Sequence[object]:
    """A copy of an array of the GO world's inputs.

    Args:
        key: the input.

    Returns:
        Its items.
    """
    value = BASE.ctx.get(key)
    return list(value) if isinstance(value, (list, tuple)) else []


def made(
    given: Kit, world: World = BASE, owner: actcore.Owner | None = None
) -> fakehub.Made:
    """A fake GitHub holding a world, with the kit's controls and gate.

    Args:
        given: the kit.
        world: the world.
        owner: the owner's messages.

    Returns:
        The hub and the verb's world.
    """
    return fakehub.holding(world, rests_of(given_of(given)), owner)


def given_of(given: Kit, decided: answer.Decided | None = None) -> fakegiven.Given:
    """What a fake GitHub's verbs rest on, from a kit.

    Args:
        given: the kit.
        decided: the decisions ``dispatch-next`` takes the head of (one ticket
            when None).

    Returns:
        The controls and the gate.
    """
    return dataclasses.replace(given.rests, decided=decided or fakegiven.work())


def rests_of(given: fakegiven.Given) -> fakehub.Rests:
    """What a fake GitHub's verbs rest on, its decisions bound to the kit.

    Args:
        given: the controls, the gate and how the decisions are made.

    Returns:
        The controls and the verb's decisions.
    """
    decided = functools.partial(given.decisions_of, kit=given)
    return fakehub.Rests(controls=given.controls, decided=decided)


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
    return ran(given, hub.act, actfacts.Asked(verb=verb, target=target, options=words))


def ran(given: Kit, world: actcore.Act, asked: actfacts.Asked) -> str:
    """Run a verb as ``act`` runs it: looked up in the decisions, then applied.

    Args:
        given: the kit.
        world: the verb's world.
        asked: the verb, its target and its options.

    Returns:
        What it said; the ``NOT DONE`` line of what stands instead.
    """
    return actverbs.run(world, asked, given.verbs)


def refused(run: Callable[[], object]) -> str:
    """Whether a call is refused.

    Args:
        run: the call.

    Returns:
        The refusal's text ("refused" when it has none), the decision that stands
        when the verb did not run, or "" when it went.
    """
    try:
        went = run()
    except REFUSALS as error:
        return str(error) or "refused"
    return str(went) if str(went).startswith(render.NOT_DONE) else ""


CHECKOUTS = fakehub.rule_checkouts(scratch.process_directory())


def brief_for(given: Kit, repo: str, *paths: str) -> tuple[str, rulefiles.Ticket]:
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
    cases: MutableMapping[str, Known],
) -> Callable[[str, str, str], Callable[[Case], Case]]:
    """The decorator that registers a case in a module's table.

    Args:
        cases: the module's table, by id.

    Returns:
        ``case(name, control, what)``, the decorator of one case.
    """

    def one(name: str, control: str, what: str) -> Callable[[Case], Case]:
        def register(run: Case) -> Case:
            cases[name] = Known(control=control, what=what, run=run)
            return run

        return register

    return one


def refusal(kit: Kit, hub: fakehub.Made, verb: str, **options: str) -> str:
    """Run a verb on the world's PR and say how it was refused.

    Args:
        kit: the kit the verbs and the gate are of.
        hub: the hub and the verb's world.
        verb: the verb.
        **options: its options (``_`` for ``-``).

    Returns:
        The refusal's text, or "" when it went.
    """
    return refused(lambda: act(kit, hub, verb, **options))
