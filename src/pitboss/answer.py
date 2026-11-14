"""The values of a decision and of the answer to what is next (keyword: one-path).

Only ``decide`` makes them; the projections pick from them and the renderers say
them. A decision has an actor, a verb and an item, and no field for a reason not
to act: an item no actor takes has no value here at all.
"""

import dataclasses
import enum
from typing import Mapping, Sequence

NOT_DONE = "NOT DONE"  # a verb whose decision is another prints the one that stands


class Actor(enum.Enum):
    """Who acts; the name is the word printed.

    Attributes:
        WORKER: a worker in a slot.
        REVIEWER: a reviewer in a slot, never the author.
        RULING: an Opus agent, no slot.
        ORCHESTRATOR: the orchestrator itself.
        OWNER: the owner.
    """

    WORKER = enum.auto()
    REVIEWER = enum.auto()
    RULING = enum.auto()
    ORCHESTRATOR = enum.auto()
    OWNER = enum.auto()


class Carried(enum.Enum):
    """The ``act`` verb that carries a decision out, which looks it up (P8).

    Attributes:
        NOTHING: no gated verb (a ticket, a review, a fix, a stop's route).
        MERGE: ``act merge`` or ``act arm``: the PR merges.
        UNDRAFT: ``act undraft``: the PR is undrafted.
    """

    NOTHING = enum.auto()
    MERGE = enum.auto()
    UNDRAFT = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Decision:
    """Who does what on which item, now.

    Attributes:
        actor: who acts.
        verb: what they do, in words.
        item: the item, ``owner/name#number``.
        title: the item's title.
        carried: the gated verb that carries it out.
        lifts: the stop line ``act override`` may lift for it, empty for none.
    """

    actor: Actor
    verb: str
    item: str
    title: str
    carried: Carried
    lifts: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Work:
    """There is work: the decisions, first to take first.

    Attributes:
        first: the first decision.
        rest: the others, in order.
        free: how many slots are free now (a datum, never a filter).
    """

    first: Decision
    rest: Sequence[Decision]
    free: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class NotEnoughWork:
    """No item of any priority label can be started: the only empty answer."""


Answer = Work | NotEnoughWork


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Decided:
    """Every decision of one world.

    Attributes:
        answer: what is next.
        by_item: the decision of each examined item that has one.
        acting: what stands instead of the ``act`` verb the world was read for;
            None when nothing does (and for any other command).
    """

    answer: Answer
    by_item: Mapping[str, Decision]
    acting: "Acting"


Standing = Decision | NotEnoughWork  # the decision that stands: the head, or none


class Why(enum.Enum):
    """Which state of GitHub, the owner or the checkout stands instead of a write.

    Attributes:
        OWNER_MESSAGE: an owner message has no disposition.
        HOLD: a hold covers the verb.
        OVER_P90: the ticket's Max-lines is over the repository's p90, with no ruling.
        STARTED: a PR closes the ticket, so a worker started it.
        NOT_OURS: the comment is not one ``pitboss act`` posted.
        TICKET_FORM: the ticket body is not in the form the ticket reader takes.
        DEFAULT_BRANCH: the branch to push to is a default branch.
        EMPTY_COMMIT: the head commit changes nothing (a body is ``act pr-edit``).
        OTHER_BRANCH: the worktree is not on the branch dispatch assigned.
        PRE_PUSH: the pre-push check did not say ok.
        KEPT_CHANGES: a worktree has changes not committed, so it is kept.
        KEPT_UNPUSHED: a worktree has a commit on no remote branch, so it is kept.
    """

    OWNER_MESSAGE = enum.auto()
    HOLD = enum.auto()
    OVER_P90 = enum.auto()
    STARTED = enum.auto()
    NOT_OURS = enum.auto()
    TICKET_FORM = enum.auto()
    DEFAULT_BRANCH = enum.auto()
    EMPTY_COMMIT = enum.auto()
    OTHER_BRANCH = enum.auto()
    PRE_PUSH = enum.auto()
    KEPT_CHANGES = enum.auto()
    KEPT_UNPUSHED = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class NotDone:
    """The verb is not done: what stands instead of it.

    Attributes:
        why: which state stands.
        line: what it is, in one line.
    """

    why: Why
    line: str


Acting = NotDone | None  # the decision on an act verb: None when nothing stands
