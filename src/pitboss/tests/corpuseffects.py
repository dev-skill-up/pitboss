"""A worker's required effects done to a recorded PR (pitboss#526, keyword: progress).

The effects come from ``workerselect.TABLE`` and are done to the PR as the shipped
command writes them: a push is another head, a hand-back is the body's ``Head:``
line naming the head and a clean ``Plan check`` of the body, read back by
``handbackderive``.
"""

import dataclasses

from .. import flow, handbackderive, shapes, headlinepattern, workerselect
from ..workerselect import Effect
from . import blank, checkcomment, pullstates

NEW_HEAD = "f" * 40


def _named(body: str, head: str) -> str:
    # the body's ``Head:`` lines name the head: the last is the one that counts
    line = f"Head: {head}"
    found = headlinepattern.HEAD_LINE.search(body)
    return headlinepattern.HEAD_LINE.sub(line, body) if found else f"{body}\n{line}\n"


def _handed(state: flow.PullState) -> flow.PullState:
    body = _named(state.pull.body, state.pull.head.sha)
    pull = dataclasses.replace(state.pull, body=body)
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


def applied(
    state: flow.PullState, task: workerselect.Task, body: str | None = None
) -> flow.PullState | None:
    """The PR after a worker did the effects its task requires.

    Args:
        state: the PR.
        task: the worker's task.
        body: the body the worker writes, when the task edits it.

    Returns:
        The PR, None when an effect cannot be done from what was recorded (a
        ticket filed, a body not given).
    """
    required = workerselect.TABLE[task].required
    edits = {Effect.EDIT_BODY, Effect.EDIT_PLAN} & required
    written = dataclasses.replace(state.pull, body=body) if body else state.pull
    pushed = dataclasses.replace(state, pull=written)
    if Effect.PUSH in required:
        head = dataclasses.replace(pushed.pull.head, sha=NEW_HEAD)
        # GitHub reads a pushed head afresh: no conflict, no check run yet
        pull = dataclasses.replace(
            pushed.pull, head=head, mergeable_state=shapes.MergeState.CLEAN
        )
        pushed = dataclasses.replace(pushed, pull=pull, checks=())
    done = _handed(pushed) if Effect.HAND_BACK in required else pushed
    unwritten = bool(edits) and body is None
    return None if unwritten or Effect.FILE_TICKET in required else done
