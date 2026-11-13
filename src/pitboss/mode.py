"""What a command line asks, as one closed type (keyword: one-path).

``parse`` maps every parse of the command line onto one ``Mode``: the questions of
what is next (``next``, the ``slots`` actions that say it, ``act dispatch-next``)
each have a constructor and a tag of their own, ``sweep`` is ``Sweep``, which
reads every open pull request, and every other command and action, which decides
nothing about a step, is ``Other``. Every dispatch on a mode is a ``match`` that
ends in ``assert_never``.
"""

import argparse
import dataclasses
import enum
from typing import Callable, Mapping, Sequence

from . import config, ledger, nextcommand


class Asked(enum.Enum):
    """Which command asks what is next.

    Attributes:
        NEXT: ``next``.
        SLOTS_NEXT: ``slots next``.
        FREE_CHECK: ``slots free-check``.
        TASKLIST: ``slots tasklist``.
        HAND_BACK: ``slots free`` and ``slots heard``, which say what the slot
            takes next.
        WATCH: ``slots watch``, whose ``SLOT FREE`` line names the first decision.
    """

    NEXT = enum.auto()
    SLOTS_NEXT = enum.auto()
    FREE_CHECK = enum.auto()
    TASKLIST = enum.auto()
    HAND_BACK = enum.auto()
    WATCH = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class WhatNext:
    """What is next: ``next``, ``slots next`` with no item, ``slots free-check``.

    Attributes:
        asked: the command that asks.
    """

    asked: Asked


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class ItemNext:
    """What is next for one item: ``next <item>`` and ``slots next <item>``.

    Attributes:
        asked: the command that asks.
        item: the item, ``owner/name#number``.
    """

    asked: Asked
    item: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class DispatchNext:
    """The one next piece of work: ``act dispatch-next``.

    Attributes:
        want: the item the caller means, empty for any.
        options: the other options (``checkout``, ``paths``, ``home``).
    """

    want: str
    options: Mapping[str, str]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Sweep:
    """Every open pull request, then what is next: ``sweep``.

    Attributes:
        task_list: the task list the sweep writes to, empty for none.
    """

    task_list: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Other:
    """A command or action that decides nothing about a step.

    Attributes:
        command: the command as typed.
    """

    command: str


Mode = WhatNext | ItemNext | DispatchNext | Sweep | Other
NAMES: Sequence[str] = ("WhatNext", "ItemNext", "DispatchNext", "Sweep", "Other")
ModeOf = Callable[[argparse.Namespace, config.Repo, Mapping[str, str]], Mode]


def _item(word: object, project: config.Repo) -> str:
    return ledger.reference(str(word), project) if word else ""


def _named(asked: Asked, words: Sequence[str], project: config.Repo) -> Mode:
    # an item form names one item in full; other words exit 2 (``nextcommand``)
    item = nextcommand.reference(words, project)
    return WhatNext(asked=asked) if item is None else ItemNext(asked=asked, item=item)


def _next(args: argparse.Namespace, project: config.Repo, _: Mapping[str, str]) -> Mode:
    ticket = getattr(args, "ticket", None)
    return _named(Asked.NEXT, [] if ticket is None else [str(ticket)], project)


def _slots_next(
    args: argparse.Namespace, project: config.Repo, _: Mapping[str, str]
) -> Mode:
    words = list(getattr(args, "words", ()) or ())
    return _named(Asked.SLOTS_NEXT, words, project)


def _asking(asked: Asked) -> ModeOf:
    def parsed(*_: object) -> Mode:
        return WhatNext(asked=asked)

    return parsed


def _dispatch_next(
    _: argparse.Namespace, project: config.Repo, options: Mapping[str, str]
) -> Mode:
    rest = {key: value for key, value in options.items() if key != "want"}
    return DispatchNext(want=_item(options.get("want"), project), options=rest)


def _sweep(args: argparse.Namespace, *_: object) -> Mode:
    return Sweep(task_list=str(getattr(args, "task_list", "") or ""))


# the commands whose second word is no action
UNACTIONED = frozenset({"next", "sweep"})
PARSES: Mapping[tuple[str, str], ModeOf] = {
    ("sweep", ""): _sweep,
    ("next", ""): _next,
    ("slots", "next"): _slots_next,
    ("slots", "free-check"): _asking(Asked.FREE_CHECK),
    ("slots", "tasklist"): _asking(Asked.TASKLIST),
    ("slots", "free"): _asking(Asked.HAND_BACK),
    ("slots", "heard"): _asking(Asked.HAND_BACK),
    ("slots", "watch"): _asking(Asked.WATCH),
    ("act", "dispatch-next"): _dispatch_next,
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
