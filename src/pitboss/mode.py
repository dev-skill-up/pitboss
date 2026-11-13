"""What a command line asks, as one closed type (keyword: one-path).

``parse`` maps every parse of the command line onto one ``Mode``; the questions of
what is next (``next``, ``slots next``, ``slots free-check``, ``act
dispatch-next``) each have a constructor of their own, and every other command and
action is ``Other``, which decides nothing about a step. Every dispatch on a mode is
a ``match`` that ends in ``assert_never``.
"""

import argparse
import dataclasses
from typing import Mapping, Sequence

from . import config, ledger


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class WhatNext:
    """What is next: ``next`` and ``slots next`` with no item.

    Attributes:
        command: the command as typed (``next``, ``slots next``).
    """

    command: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class ItemNext:
    """What is next for one item: ``next <item>`` and ``slots next <item>``.

    Attributes:
        command: the command as typed.
        item: the item, ``owner/name#number``.
    """

    command: str
    item: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class FreeCheck:
    """Whether a free slot has work: ``slots free-check``."""


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


Mode = WhatNext | ItemNext | FreeCheck | DispatchNext | Other
NAMES: Sequence[str] = ("WhatNext", "ItemNext", "FreeCheck", "DispatchNext", "Other")


def _item(words: Sequence[str], project: config.Repo) -> str:
    return ledger.reference(words[0], project) if words and words[0] else ""


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
    action = str(getattr(args, "action", "") or "")
    verb = str(getattr(args, "verb", "") or "")
    if name == "next":
        ticket = getattr(args, "ticket", None)
        if ticket is None:
            return WhatNext(command="next")
        return ItemNext(command="next", item=_item([ticket], project))
    if name == "slots" and action == "next":
        words = list(getattr(args, "words", ()) or ())
        if not words:
            return WhatNext(command="slots next")
        return ItemNext(command="slots next", item=_item(words, project))
    if name == "slots" and action == "free-check":
        return FreeCheck()
    if name == "act" and verb == "dispatch-next":
        rest = {key: value for key, value in options.items() if key != "want"}
        want = _item([options.get("want", "")], project)
        return DispatchNext(want=want, options=rest)
    return Other(command=" ".join(filter(None, [name, action or verb])))
