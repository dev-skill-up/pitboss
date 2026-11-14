"""What a mode asks of the one read and of the decisions (keyword: one-path).

``mode.question_of`` is the one dispatch on a mode that says it.
"""

import dataclasses
import enum


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
    """

    answers: Answers
    item: str


def asking(answers: Answers, item: str) -> Question:
    """What a mode asks that reads no more than the item it names.

    Args:
        answers: what it prints of the decisions.
        item: the item it names, empty for none.

    Returns:
        The question.
    """
    return Question(answers=answers, item=item)


LISTED = asking(Answers.LIST, "")
QUIET = asking(Answers.NOTHING, "")
