"""What a command line asks, as one closed type (keyword: one-path).

``parse`` maps every parse of the command line onto one ``Mode``: each command,
action and item form that asks of the decisions has a constructor of its own
(``next`` is ``Next``, ``next <item>`` is ``NextItem``, ``act merge <item>`` is
``Merge``, ...), ``push --mechanical`` is ``MechanicalPush``, and every other
command and action, which asks nothing of the decisions, is ``Other``. Every
dispatch on a mode is a ``match`` that ends in ``assert_never``.
"""

import argparse
import dataclasses
import enum
import typing
from dataclasses import dataclass
from typing import Callable, Mapping, Protocol, Sequence, assert_never

from . import config, ledger, nextcommand


@dataclass(frozen=True, slots=True, kw_only=True)
class Next:
    """``next``: what is next."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SlotsNext:
    """``slots next``: what is next, for a slot."""


@dataclass(frozen=True, slots=True, kw_only=True)
class FreeCheck:
    """``slots free-check``: whether a slot is free, and what it takes."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Tasks:
    """``slots tasklist``: the task list of what is next."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Free:
    """``slots free``: a slot handed back, and what it takes next."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Heard:
    """``slots heard``: a hand-back heard, and what the slot takes next."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Watch:
    """``slots watch``: its ``SLOT FREE`` line names the first decision."""


@dataclass(frozen=True, slots=True, kw_only=True)
class NextItem:
    """``next <item>``: the item's decision.

    Attributes:
        item: the item, ``owner/name#number``.
    """

    item: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SlotsNextItem:
    """``slots next <item>``: the item's decision, for a slot.

    Attributes:
        item: the item, ``owner/name#number``.
    """

    item: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Merge:
    """``act merge <item>``: runs when the item's decision is the merge.

    Attributes:
        item: the item, ``owner/name#number``.
    """

    item: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Arm:
    """``act arm <item>``: runs when the item's decision is to arm it.

    Attributes:
        item: the item, ``owner/name#number``.
    """

    item: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Undraft:
    """``act undraft <item>``: runs when the item's decision is the undraft.

    Attributes:
        item: the item, ``owner/name#number``.
    """

    item: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PinsReview:
    """``pins-review <item>``: reviews a relock's pins.

    Attributes:
        item: the item, ``owner/name#number``.
    """

    item: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DispatchNext:
    """The one next piece of work: ``act dispatch-next``.

    Attributes:
        want: the item the caller means, empty for any.
        options: the other options (``checkout``, ``paths``, ``home``).
    """

    want: str
    options: Mapping[str, str]


@dataclass(frozen=True, slots=True, kw_only=True)
class Sweep:
    """Every open pull request, then what is next: ``sweep``.

    Attributes:
        task_list: the task list the sweep writes to, empty for none.
    """

    task_list: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OverrideAct:
    """``act override <item> stop=... reason=...``: lift one stop of its decision.

    Attributes:
        item: the pull request, ``owner/name#number``.
        stop: the stop line it lifts, which must be a stop of the item's decision.
        reason: the ruling the override rests on.
    """

    item: str
    stop: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MechanicalPush:
    """``push --mechanical``: a push free of the hold for a mechanical red.

    Attributes:
        arguments: the arguments after ``push``, which name the branches pushed.
    """

    arguments: Sequence[str]


@dataclass(frozen=True, slots=True, kw_only=True)
class Other:
    """A command or action that decides nothing about a step.

    Attributes:
        command: the command as typed.
    """

    command: str


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


@dataclass(frozen=True, slots=True, kw_only=True)
class Question:
    """What a mode asks of the one read and of the decisions.

    Attributes:
        answers: what it prints of the decisions.
        item: the item it names, empty for none.
        every_pull: whether it reads every open pull request (the sweep).
        pushing: whether it reads the pull requests of the branches it pushes.
        pushed: the arguments of that push.
    """

    answers: Answers
    item: str
    every_pull: bool
    pushing: bool
    pushed: Sequence[str]


Listing = Next | SlotsNext | FreeCheck | Tasks | Free | Heard | Watch
Naming = NextItem | SlotsNextItem | Merge | Arm | Undraft | PinsReview
Mode = Listing | Naming | DispatchNext | Sweep | OverrideAct | MechanicalPush | Other
NAMES: Sequence[str] = tuple(each.__name__ for each in typing.get_args(Mode))
ModeOf = Callable[[argparse.Namespace, config.Repo, Mapping[str, str]], Mode]


class Named(Protocol):
    """A constructor of a mode that names one item."""

    def __call__(self, *, item: str) -> Mode:
        """The mode.

        Args:
            item: the item, ``owner/name#number``.

        Returns:
            The mode that names it.
        """


def _item(word: object, project: config.Repo) -> str:
    return ledger.reference(str(word), project) if word else ""


def _named(
    bare: Callable[[], Mode], named: Named, words: Sequence[str], project: config.Repo
) -> Mode:
    # an item form names one item in full; other words exit 2 (``nextcommand``)
    item = nextcommand.reference(words, project)
    return bare() if item is None else named(item=item)


def _next(args: argparse.Namespace, project: config.Repo, _: Mapping[str, str]) -> Mode:
    ticket = getattr(args, "ticket", None)
    return _named(Next, NextItem, [] if ticket is None else [str(ticket)], project)


def _slots_next(
    args: argparse.Namespace, project: config.Repo, _: Mapping[str, str]
) -> Mode:
    words = list(getattr(args, "words", ()) or ())
    return _named(SlotsNext, SlotsNextItem, words, project)


def _asking(bare: Callable[[], Mode]) -> ModeOf:
    def parsed(*_: object) -> Mode:
        return bare()

    return parsed


def _dispatch_next(
    _: argparse.Namespace, project: config.Repo, options: Mapping[str, str]
) -> Mode:
    rest = {key: value for key, value in options.items() if key != "want"}
    return DispatchNext(want=_item(options.get("want"), project), options=rest)


def _acting(named: Named, field: str) -> ModeOf:
    # an item the command names in its argument ``field``
    def parsed(args: argparse.Namespace, project: config.Repo, *_: object) -> Mode:
        return named(item=_item(getattr(args, field, ""), project))

    return parsed


def _override(
    args: argparse.Namespace, project: config.Repo, options: Mapping[str, str]
) -> Mode:
    item = _item(getattr(args, "target", ""), project)
    stop, reason = options.get("stop", ""), options.get("reason", "")
    return OverrideAct(item=item, stop=stop, reason=reason)


def _push(args: argparse.Namespace, *_: object) -> Mode:
    # only ``--mechanical`` asks of the decisions (keyword: mechanical-fix)
    if not getattr(args, "mechanical", False):
        return Other(command="push")
    return MechanicalPush(arguments=list(getattr(args, "git_arguments", ()) or ()))


def _sweep(args: argparse.Namespace, *_: object) -> Mode:
    return Sweep(task_list=str(getattr(args, "task_list", "") or ""))


# the commands whose second word is no action
UNACTIONED = frozenset({"next", "sweep", "pins-review", "push"})
PARSES: Mapping[tuple[str, str], ModeOf] = {
    ("sweep", ""): _sweep,
    ("next", ""): _next,
    ("slots", "next"): _slots_next,
    ("slots", "free-check"): _asking(FreeCheck),
    ("slots", "tasklist"): _asking(Tasks),
    ("slots", "free"): _asking(Free),
    ("slots", "heard"): _asking(Heard),
    ("slots", "watch"): _asking(Watch),
    ("act", "dispatch-next"): _dispatch_next,
    ("act", "merge"): _acting(Merge, "target"),
    ("act", "arm"): _acting(Arm, "target"),
    ("act", "undraft"): _acting(Undraft, "target"),
    ("act", "override"): _override,
    ("pins-review", ""): _acting(PinsReview, "pull"),
    ("push", ""): _push,
}


def parse(
    args: argparse.Namespace, project: config.Repo, options: Mapping[str, str]
) -> Mode:
    """What a parsed command line asks.

    Args:
        args: the parsed arguments.
        project: the project's repository, for a short reference.
        options: an ``act`` command's ``name=value`` options.

    Returns:
        The mode.
    """
    name = str(getattr(args, "__gather_name__", ""))
    action = str(getattr(args, "action", "") or getattr(args, "verb", "") or "")
    if name in UNACTIONED:
        action = ""
    found = PARSES.get((name, action))
    if found is not None:
        return found(args, project, options)
    return Other(command=" ".join(filter(None, [name, action])))


def _question(answers: Answers, item: str) -> Question:
    return Question(
        answers=answers, item=item, every_pull=False, pushing=False, pushed=()
    )


LISTED = _question(Answers.LIST, "")
QUIET = _question(Answers.NOTHING, "")
EVERY = dataclasses.replace(QUIET, every_pull=True)


def question_of(chosen: Mode) -> Question:
    """What a mode asks: the one dispatch on its constructor.

    Args:
        chosen: the mode.

    Returns:
        What it answers, the item it names and what it reads beyond it.
    """
    match chosen:
        case Next() | SlotsNext() | FreeCheck() | Tasks() | Free() | Heard() | Watch():
            return LISTED
        case NextItem() | SlotsNextItem() | Merge() | Arm() | Undraft() | PinsReview():
            return _question(Answers.ITEM, chosen.item)
        case OverrideAct():
            return _question(Answers.NOTHING, chosen.item)
        case DispatchNext() | Other():
            return QUIET
        case Sweep():
            return EVERY
        case MechanicalPush():
            return dataclasses.replace(QUIET, pushing=True, pushed=chosen.arguments)
        case _:  # pragma: no cover
            assert_never(chosen)


def item_of(chosen: Mode) -> str:
    """The item a mode names.

    Args:
        chosen: the mode.

    Returns:
        The item of an item form or an override, empty for any other.
    """
    return question_of(chosen).item
