"""What a command line asks, as one closed type (keyword: one-path).

``parse`` maps every parse of the command line onto one ``Mode``; the questions of
what is next (``next``, ``slots next``, ``slots free-check``, ``act
dispatch-next``) each have a constructor and a tag of their own, and every other
command and action is ``Other``, which decides nothing about a step. Every dispatch
on a mode is a ``match`` that ends in ``assert_never``.
"""

import argparse
import dataclasses
import enum
from typing import Callable, Mapping, Sequence

from . import config, ledger


class Asked(enum.Enum):
    """Which command asks what is next.

    Attributes:
        NEXT: ``next``.
        SLOTS_NEXT: ``slots next``.
        FREE_CHECK: ``slots free-check``.
    """

    NEXT = enum.auto()
    SLOTS_NEXT = enum.auto()
    FREE_CHECK = enum.auto()


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
class Other:
    """A command or action that decides nothing about a step.

    Attributes:
        command: the command as typed.
    """

    command: str


Mode = WhatNext | ItemNext | DispatchNext | Other
NAMES: Sequence[str] = ("WhatNext", "ItemNext", "DispatchNext", "Other")
ModeOf = Callable[[argparse.Namespace, config.Repo, Mapping[str, str]], Mode]


def _item(word: object, project: config.Repo) -> str:
    return ledger.reference(str(word), project) if word else ""


def _next(args: argparse.Namespace, project: config.Repo, _: Mapping[str, str]) -> Mode:
    ticket = getattr(args, "ticket", None)
    if ticket is None:
        return WhatNext(asked=Asked.NEXT)
    return ItemNext(asked=Asked.NEXT, item=_item(ticket, project))


def _slots_next(
    args: argparse.Namespace, project: config.Repo, _: Mapping[str, str]
) -> Mode:
    words = list(getattr(args, "words", ()) or ())
    if not words:
        return WhatNext(asked=Asked.SLOTS_NEXT)
    return ItemNext(asked=Asked.SLOTS_NEXT, item=_item(words[0], project))


def _free_check(*_: object) -> Mode:
    return WhatNext(asked=Asked.FREE_CHECK)


def _dispatch_next(
    _: argparse.Namespace, project: config.Repo, options: Mapping[str, str]
) -> Mode:
    rest = {key: value for key, value in options.items() if key != "want"}
    return DispatchNext(want=_item(options.get("want"), project), options=rest)


PARSES: Mapping[tuple[str, str], ModeOf] = {
    ("next", ""): _next,
    ("slots", "next"): _slots_next,
    ("slots", "free-check"): _free_check,
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
    if name == "next":
        action = ""
    found = PARSES.get((name, action))
    if found is not None:
        return found(args, project, options)
    return Other(command=" ".join(filter(None, [name, action])))
