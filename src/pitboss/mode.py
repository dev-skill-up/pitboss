"""What a command line asks, as one closed type (keyword: one-path).

``parse`` maps every parse of the command line onto one ``Mode``: each command,
action and item form that asks of the decisions has a constructor of its own
(``next`` is ``Next``, ``next <item>`` is ``NextItem``, ``act merge <item>`` is
``Merge``, ...), ``push --mechanical`` is ``MechanicalPush``, every other act
verb is ``ActOn`` of its ``gateverbs.Verb``, and every other command and action,
which asks nothing of the decisions, is ``Unasked`` of its ``modecommand.Command``:
a new command or verb has no mode until it is named, and ``parse`` exits 2 for it.
Every dispatch on a mode is a ``match`` that ends in ``assert_never``.
"""

import argparse
import typing
from dataclasses import dataclass
from typing import Callable, Mapping, Protocol, Sequence, assert_never

from . import config, gateverbs, modecommand, nextcommand, slotbook
from .modequestion import LISTED, QUIET, Answers, Question, asking


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
class DispatchAny:
    """The one next piece of work, whatever it is: ``act dispatch-next``.

    Attributes:
        options: the other options (``checkout``, ``paths``, ``home``).
    """

    options: Mapping[str, str]


@dataclass(frozen=True, slots=True, kw_only=True)
class DispatchWanted:
    """The one next piece of work, when it is the item meant: ``want=<item>``.

    Attributes:
        want: the item the caller means.
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
class ActOn:
    """``act <verb> <target>``: a write its decision says is done or not done.

    Attributes:
        verb: the verb (none of merge, arm, undraft, override and dispatch-next,
            which have modes of their own).
        target: the target as typed (``owner/name#N``, ``owner/name`` or ``all``).
        item: the item it names in full, empty when it names a repository or all.
        options: its ``name=value`` options.
    """

    verb: gateverbs.OwnVerb
    target: str
    item: str
    options: Mapping[str, str]


@dataclass(frozen=True, slots=True, kw_only=True)
class Unasked:
    """A command or action that asks nothing of the decisions.

    Attributes:
        command: which one.
    """

    command: modecommand.Command


Listing = Next | SlotsNext | FreeCheck | Tasks | Free | Heard | Watch
Naming = NextItem | SlotsNextItem | Merge | Arm | Undraft | PinsReview
Dispatching = DispatchAny | DispatchWanted
Acting = Dispatching | OverrideAct | ActOn
Mode = Listing | Naming | Acting | Sweep | MechanicalPush | Unasked
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
    return slotbook.reference(str(word), project) if word else ""


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
    want = _item(options.get("want"), project)
    return (
        DispatchWanted(want=want, options=rest) if want else DispatchAny(options=rest)
    )


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
        return Unasked(command=modecommand.Command.PUSH)
    return MechanicalPush(arguments=list(getattr(args, "git_arguments", ()) or ()))


def _verb(verb: gateverbs.OwnVerb) -> ModeOf:
    # an act verb with no mode of its own
    def parsed(
        args: argparse.Namespace, project: config.Repo, options: Mapping[str, str]
    ) -> Mode:
        target = str(getattr(args, "target", ""))
        item = _item(target, project) if "#" in target else ""
        return ActOn(verb=verb, target=target, item=item, options=options)

    return parsed


def _sweep(args: argparse.Namespace, *_: object) -> Mode:
    return Sweep(task_list=str(getattr(args, "task_list", "") or ""))


UNACTIONED = frozenset({"next", "sweep", "pins-review", "push"})  # no action word
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
    **{("act", each.value): _verb(each) for each in gateverbs.ACTED_ON},
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

    Raises:
        SystemExit: no mode names the command (exit 2).
    """
    name = str(getattr(args, "__gather_name__", ""))
    action = str(getattr(args, "action", "") or getattr(args, "verb", "") or "")
    if name in UNACTIONED:
        action = ""
    found = PARSES.get((name, action))
    if found is not None:
        return found(args, project, options)
    words = " ".join(filter(None, [name, action]))
    if words not in modecommand.UNASKED:
        raise SystemExit(f"{words}: no mode names it (keyword: one-path)")
    return Unasked(command=modecommand.UNASKED[words])


def question_of(chosen: Mode) -> Question:
    """What a mode asks: the one dispatch on its constructor.

    Args:
        chosen: the mode.

    Returns:
        What it answers and the item it names.
    """
    match chosen:
        case Next() | SlotsNext() | FreeCheck() | Tasks() | Free() | Heard() | Watch():
            return LISTED
        case NextItem() | SlotsNextItem() | Merge() | Arm() | Undraft() | PinsReview():
            return asking(Answers.ITEM, chosen.item)
        case OverrideAct() | ActOn():
            return asking(Answers.NOTHING, chosen.item)
        case DispatchWanted():
            return asking(Answers.NOTHING, chosen.want)
        case DispatchAny() | Unasked() | Sweep() | MechanicalPush():
            return QUIET
        case _:  # pragma: no cover
            assert_never(chosen)


def item_of(chosen: Mode) -> str:
    """The item a mode names.

    Args:
        chosen: the mode.

    Returns:
        The item it names, empty for none.
    """
    return question_of(chosen).item
