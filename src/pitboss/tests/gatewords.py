"""The word and lines of the gate's stops, as the act tests compare (keyword: gate)."""

import dataclasses
import enum
from typing import Sequence

from ..gatestop import Stop


class Word(enum.Enum):
    """Whether the action may be taken.

    Attributes:
        GO: no stop.
        STOP: a stop; the lines say which.
    """

    GO = enum.auto()
    STOP = enum.auto()


GO = Word.GO
STOP = Word.STOP


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Answer:
    """What the gate says of an action.

    Attributes:
        word: ``GO`` or ``STOP``.
        lines: the stop lines.
        stops: the stops, with their routes.
    """

    word: Word
    lines: Sequence[str] = ()
    stops: Sequence[Stop] = ()
