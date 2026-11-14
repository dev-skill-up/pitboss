"""The act verbs ``dispatch-next`` and ``push``, run over a kit (keyword: act-verbs)."""

import dataclasses
import pathlib

from .. import actcore, actfacts, answer
from . import fakehub
from .knownkit import BASE, REPO, Kit, given_of, made, ran, rests_of


def dispatch(given: Kit, decided: answer.Decided, **options: str) -> str:
    """Run ``dispatch-next`` over the decisions of a world.

    Args:
        given: the kit.
        decided: the decisions.
        **options: ``want``.

    Returns:
        The item it answers.
    """
    hub = fakehub.holding(BASE, rests_of(given_of(given, decided)))
    world = dataclasses.replace(
        hub.act,
        questions=dataclasses.replace(
            hub.act.questions,
            decided=lambda asked: decided,
        ),
    )
    target = actcore.Target(repo=REPO)
    asked = actfacts.Asked(verb="dispatch-next", target=target, options=options)
    return ran(given, world, asked)


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
    world = dataclasses.replace(made(given).act, prepush=lambda: prepush)
    return push_in(given, world, worktree, actcore.Target(repo=REPO))


def push_in(
    given: Kit, world: actcore.Act, worktree: pathlib.Path, target: actcore.Target
) -> str:
    """Run ``push`` of a worktree to ``worker/7`` in a verb's world.

    Args:
        given: the kit.
        world: the verb's world.
        worktree: the worktree.
        target: the repository, and the PR when there is one.

    Returns:
        What it said.
    """
    options = {"worktree": str(worktree), "branch": "worker/7"}
    asked = actfacts.Asked(verb="push", target=target, options=options)
    return ran(given, world, asked)
