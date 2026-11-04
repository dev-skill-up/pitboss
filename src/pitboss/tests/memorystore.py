"""A pull request in memory, for the tests of splitting a body (pitboss#177)."""

import dataclasses
import functools
import itertools
from typing import MutableMapping, MutableSequence, Sequence

from .. import evidencesplit

URL = "https://github.com/owner/project/pull/7#issuecomment-"
OTHER = evidencesplit.Comment(number=1, url=URL + "1", body="hello")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Memory:
    """A pull request in memory: a description and comments.

    Attributes:
        stored: the comments of this tool, by id.
        description: the description, in a list of one.
        ids: the next ids.
        log: what was done, in order.
    """

    stored: MutableMapping[int, evidencesplit.Comment] = dataclasses.field(
        default_factory=dict
    )
    description: MutableSequence[str] = dataclasses.field(default_factory=list)
    ids: "itertools.count[int]" = dataclasses.field(
        default_factory=lambda: itertools.count(100)
    )
    log: MutableSequence[str] = dataclasses.field(default_factory=list)


def comments(memory: Memory) -> Sequence[evidencesplit.Comment]:
    """List the comments: another person's, then the tool's.

    Args:
        memory: the pull request.

    Returns:
        The comments.
    """
    return [OTHER, *memory.stored.values()]


def edit(
    memory: Memory, number: int, body: str, verb: str = "edit"
) -> evidencesplit.Comment:
    """Replace the text of a comment.

    Args:
        memory: the pull request.
        number: the comment.
        body: the text.
        verb: what to log.

    Returns:
        The comment.
    """
    memory.log.append(f"{verb} {number}")
    memory.stored[number] = evidencesplit.Comment(
        number=number, url=f"{URL}{number}", body=body
    )
    return memory.stored[number]


def post(memory: Memory, body: str) -> evidencesplit.Comment:
    """Add a comment.

    Args:
        memory: the pull request.
        body: the text.

    Returns:
        The comment.
    """
    return edit(memory, next(memory.ids), body, "post")


def delete(memory: Memory, number: int) -> None:
    """Remove a comment.

    Args:
        memory: the pull request.
        number: the comment.
    """
    memory.log.append(f"delete {number}")
    del memory.stored[number]


def set_body(memory: Memory, body: str) -> None:
    """Set the description.

    Args:
        memory: the pull request.
        body: the text.
    """
    memory.log.append("body")
    memory.description[:] = [body]


def store_of(memory: Memory) -> evidencesplit.Store:
    """The store of a pull request in memory.

    Args:
        memory: the pull request.

    Returns:
        The store.
    """
    return evidencesplit.Store(
        comments=functools.partial(comments, memory),
        post=functools.partial(post, memory),
        edit=functools.partial(edit, memory),
        delete=functools.partial(delete, memory),
        set_body=functools.partial(set_body, memory),
    )
