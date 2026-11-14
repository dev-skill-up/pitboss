"""The kit the known cases run on, every control as pitboss ships it.

Plan part: 6.5 (the known cases run on what pitboss ships).
"""

import functools
import json

from .. import actcore, actverbs, answer, blockedstep, config, decide, gate
from .. import headsignals, rounds, straycomments
from .. import gatefacts
from .. import gatepolicy, listed, parsing, pullfacts, reviews, steps, world
from ..actport import Pull
from . import fakedecider, fakegiven, fakehub, flowread
from . import knownkit
from .fakes import pull_body
from .knownkit import Kit


def _facts(repo: config.Repo, number: int, step: steps.Next) -> pullfacts.PullRead:
    # the PR as read, with the flow's state that gives its step
    facts = pullfacts.PullFacts(
        repo=repo,
        pull=parsing.pull(json.dumps(pull_body(number))),
        checks=(),
        review=None,
        standing=reviews.Standing.NONE,
        step=step,
        signals=headsignals.NONE,
        unreadable=straycomments.NONE,
        review_rounds=rounds.NONE,
        relock=False,
    )
    merging = step.step is steps.Step.MERGE
    return flowread.read_of(facts, flowread.MERGING if merging else flowread.UNDRAFTING)


def pull_record(
    name: str, pull: Pull, step: steps.Next, gated: gatefacts.Gate | None
) -> world.PullRecord:
    """The record ``next`` makes of a PR of the hub at a step (P7: ``decide_item``).

    Args:
        name: the PR, ``owner/name#number``.
        pull: its JSON on the hub.
        step: its step.
        gated: what its action is gated on; None when no row stops it.

    Returns:
        The record.
    """
    slug, number = name.split("#")
    repo = config.make_repo(*slug.split("/"))
    return world.PullRecord(
        row=listed.listed_row(repo, "relock/", {**pull_body(int(number)), **pull}),
        facts=_facts(repo, int(number), step),
        blocked_by=blockedstep.Closure(found=[], looped=False),
        shared=[],
        blockers=[],
        stuck=[],
        gated=gated,
        failures={},
    )


def decision_of(
    name: str, pull: Pull, step: steps.Next, gated: gatefacts.Gate | None
) -> answer.Decision | None:
    """The decision of a PR of the hub at a step, by the one item decider (P7).

    Args:
        name: the PR, ``owner/name#number``.
        pull: its JSON on the hub.
        step: its step.
        gated: what its action is gated on; None when no row stops it.

    Returns:
        ``decide.decide_item`` of its record.
    """
    return decide.decide_item(pull_record(name, pull, step, gated))


@functools.cache
def rests() -> fakegiven.Given:
    """The gate and the act verbs' controls as pitboss ships them.

    Returns:
        What a fake GitHub's verbs rest on.
    """
    return fakegiven.Given(
        controls=actcore.Controls(),
        gating=gate.stops_for,
        policy=gatepolicy.shipped(),
        deciding=decision_of,
        decisions_of=fakedecider.Decider,
    )


def shipped() -> Kit:
    """Every control as pitboss ships it.

    Returns:
        The kit.
    """
    return Kit(rests=rests(), verbs=actverbs.VERBS)


GIVEN = shipped()


def refusal(hub: fakehub.Made, verb: str, **options: str) -> str:
    """Run a verb of the shipped kit on the world's PR and say how it was refused.

    Args:
        hub: the hub and the verb's world.
        verb: the verb.
        **options: its options.

    Returns:
        The refusal's text, or "" when it went.
    """
    return knownkit.refusal(GIVEN, hub, verb, **options)
