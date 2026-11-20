"""What a mode asks of the one read and of the decisions (keyword: one-path).

``mode.question_of`` is the one dispatch on a mode that says it.
"""

import dataclasses
import enum
from typing import Sequence


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Extent:
    """How much a command asks to be read.

    Attributes:
        named: the items examined whatever the walk reaches (the item the
            command names).
        every_pull: whether every open pull request is examined (the sweep).
        pushing: whether the open pull requests of the branches a ``git push``
            pushes are named too (``push --mechanical``, keyword: mechanical-fix).
        pushed: the arguments of that push, which name its branches.
        forced: the named items taken whatever keeps them (``slots next
            --force``, keyword: force).
    """

    named: Sequence[str]
    every_pull: bool
    pushing: bool
    pushed: Sequence[str]
    forced: Sequence[str]


def naming(items: Sequence[str]) -> Extent:
    """The extent of a command that names items.

    Args:
        items: the items, ``owner/name#number`` each (none for the walk alone).

    Returns:
        The extent.
    """
    return Extent(named=items, every_pull=False, pushing=False, pushed=(), forced=())


EVERY_PULL = Extent(named=(), every_pull=True, pushing=False, pushed=(), forced=())


def pushing(arguments: Sequence[str]) -> Extent:
    """The extent of ``push --mechanical``: the pull requests of its branches.

    Args:
        arguments: the push's arguments.

    Returns:
        The extent.
    """
    return Extent(named=(), every_pull=False, pushing=True, pushed=arguments, forced=())


class Answers(enum.Enum):
    """What a mode prints of the decisions.

    Attributes:
        LIST: the answer of what is next, with its tail.
        ITEM: the decision of the item it names.
        NOTHING: no answer of its own.
    """

    LIST = enum.auto()
    ITEM = enum.auto()
    NOTHING = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Question:
    """What a mode asks of the one read and of the decisions.

    Attributes:
        answers: what it prints of the decisions.
        item: the item it names, empty for none.
        extent: what its one read reads (the item it names, every PR, a push).
    """

    answers: Answers
    item: str
    extent: Extent


def asking(answers: Answers, item: str) -> Question:
    """What a mode asks that reads no more than the item it names.

    Args:
        answers: what it prints of the decisions.
        item: the item it names, empty for none.

    Returns:
        The question.
    """
    named = naming([item] if item else [])
    return Question(answers=answers, item=item, extent=named)


def forcing(item: str) -> Question:
    """What ``slots next --force <item>`` asks: the item, whatever keeps it.

    Args:
        item: the item.

    Returns:
        The question.
    """
    named = dataclasses.replace(naming([item]), forced=[item])
    return Question(answers=Answers.ITEM, item=item, extent=named)


LISTED = asking(Answers.LIST, "")
QUIET = asking(Answers.NOTHING, "")
SWEEPING = Question(answers=Answers.NOTHING, item="", extent=EVERY_PULL)  # the sweep


def pushes(arguments: Sequence[str]) -> Question:
    """What ``push --mechanical`` asks: no answer, the pull requests of its branches.

    Args:
        arguments: the push's arguments.

    Returns:
        The question.
    """
    return Question(answers=Answers.NOTHING, item="", extent=pushing(arguments))
