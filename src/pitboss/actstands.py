"""What GitHub's state decides instead of a write (plan 6.1, 6.5; keyword: act-verbs).

A verb refused for what it is given (an option, the checkout, a file's form) raises
``Refused``; a verb that GitHub's state stops is no exception but this value: an
owner message with no disposition, a hold, a line that is no stop of the item's
decision, a size over the repository's p90, a ticket a PR started, a comment
pitboss did not post, a push the remote does not hold.
"""

import dataclasses
import enum


class Why(enum.Enum):
    """Which state of GitHub stands instead of the write.

    Attributes:
        OWNER_MESSAGE: an owner message has no disposition.
        HOLD: a hold covers the verb.
        NOT_A_STOP: the override names no stop of the item's decision that it lifts.
        OVER_P90: the ticket's Max-lines is over the repository's p90, with no ruling.
        STARTED: a PR closes the ticket, so a worker started it.
        NOT_OURS: the comment is not one ``pitboss act`` posted.
        NOT_PUSHED: the remote branch does not hold the head pushed.
    """

    OWNER_MESSAGE = enum.auto()
    HOLD = enum.auto()
    NOT_A_STOP = enum.auto()
    OVER_P90 = enum.auto()
    STARTED = enum.auto()
    NOT_OURS = enum.auto()
    NOT_PUSHED = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Stands:
    """The state that stands instead of the write; nothing was written.

    Attributes:
        why: which state it is.
        line: what it is, in one line.
    """

    why: Why
    line: str


Said = str | Stands  # what a verb answers: what it did, or what stands instead
