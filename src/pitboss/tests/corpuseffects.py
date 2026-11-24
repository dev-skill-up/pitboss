"""A worker's required effects done to a recorded PR (pitboss#526, keyword: progress).

The effects come from ``workerselect.TABLE`` and are done to the PR as the shipped
command writes them: a push is another head, a hand-back is the body's ``Head:``
line naming the head and a clean ``Plan check`` of the body, read back by
``handbackderive``.
"""

import dataclasses
from typing import AbstractSet

from .. import flow, handbackderive, shapes, headlinepattern, workerselect
from ..workerselect import Effect
from . import blank, checkcomment, pullstates

NEW_HEAD = "f" * 40


def _named(body: str, head: str) -> str:
    # the body's ``Head:`` lines name the head: the last is the one that counts
    line = f"Head: {head}"
    found = headlinepattern.HEAD_LINE.search(body)
    return headlinepattern.HEAD_LINE.sub(line, body) if found else f"{body}\n{line}\n"


def _rebodied(state: flow.PullState, body: str) -> flow.PullState:
    return dataclasses.replace(state, pull=dataclasses.replace(state.pull, body=body))


def _handed(state: flow.PullState) -> flow.PullState:
    body = _named(state.pull.body, state.pull.head.sha)
    pull = _rebodied(state, body).pull
    check = dataclasses.replace(
        blank.COMMENT,
        body=checkcomment.clean_text(body),
        author_association=sorted(state.trusted)[0],
        created_at="2099-01-01T00:00:00Z",
    )
    comments = [*state.comments, check]
    derived = handbackderive.derive(pull, comments, state.trusted)
    again = dataclasses.replace(state, pull=pull, comments=comments)
    return pullstates.with_recorded(again, handed=derived)


def _written(
    state: flow.PullState, body: str | None, required: AbstractSet[Effect]
) -> flow.PullState:
    # the body the worker writes, when its effects edit it
    edits = bool({Effect.EDIT_BODY, Effect.EDIT_PLAN} & required)
    return _rebodied(state, body) if body and edits else state


def _pushed(state: flow.PullState, required: AbstractSet[Effect]) -> flow.PullState:
    if Effect.PUSH not in required:
        return state
    head = dataclasses.replace(state.pull.head, sha=NEW_HEAD)
    # GitHub reads a pushed head afresh: no conflict, no check run yet
    clean = dataclasses.replace(state.pull, mergeable_state=shapes.MergeState.CLEAN)
    pull = dataclasses.replace(clean, head=head)
    return dataclasses.replace(state, pull=pull, checks=())


def applied(
    state: flow.PullState,
    task: workerselect.Task,
    body: str | None = None,
    effects: AbstractSet[Effect] | None = None,
) -> flow.PullState:
    """The PR after a worker did the effects its task requires.

    A ticket filed is outside the PR (``workerselect.OUTSIDE``), so it changes
    nothing here.

    Args:
        state: the PR.
        task: the worker's task.
        body: the body the worker writes, when the task edits it.
        effects: what the worker does, the table's required effects of the task
            when not given (a proof gives the effects of a table it was handed).

    Returns:
        The PR.
    """
    required = workerselect.TABLE[task].required if effects is None else effects
    pushed = _pushed(_written(state, body, required), required)
    return _handed(pushed) if Effect.HAND_BACK in required else pushed
