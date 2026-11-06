"""The names a ticket's Done-when uses that do not exist (pitboss#231).

Tickets are written by hand, and nothing checked the names they use: pitboss#182
asked for a brief that does not exist and a worker lost a round finding out.
``pitboss next TICKET`` prints a ``MISSING NAMES`` line for a ticket that no PR
fixes yet when its Done-when names, in backticks, a ``brief.Kind``, a file path
or a ``pitboss`` command that is not there (keyword: done-when-names).
"""

import dataclasses
import pathlib
import re
from typing import AbstractSet, Sequence

LABEL = "MISSING NAMES"
_DONE_WHEN = re.compile(r"Done-when\s*:(.*?)(?:\n[ \t]*\n|\Z)", re.DOTALL)
_SPAN = re.compile(r"`([^`\n]+)`")
_KIND = re.compile(r"^(?:brief\.)?Kind\.([A-Z][A-Z_]*)$")
_COMMAND = re.compile(r"^pitboss\s+([a-z][a-z-]*)\b")
# a path has a directory and a file with an extension; no URL, no glob, no ref
_PATH = re.compile(r"^[\w.-]+(?:/[\w.-]+)+\.\w+$")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Names:
    """What a Done-when names.

    Attributes:
        kinds: the ``brief.Kind`` members it names.
        paths: the file paths it names.
        commands: the ``pitboss`` commands it names.
    """

    kinds: Sequence[str]
    paths: Sequence[str]
    commands: Sequence[str]


def done_when(body: str) -> str:
    """The Done-when paragraph of a ticket.

    Args:
        body: the ticket's text.

    Returns:
        The paragraph after ``Done-when:``, or "" when there is none.
    """
    found = _DONE_WHEN.search(body)
    return found.group(1) if found else ""


def names_in(text: str) -> Names:
    """The names a text puts in backticks, once each, in order.

    Args:
        text: a Done-when.

    Returns:
        The kinds, file paths and commands.
    """
    kinds: dict[str, None] = {}
    paths: dict[str, None] = {}
    commands: dict[str, None] = {}
    for span in _SPAN.findall(text):
        word = span.strip()
        if member := _KIND.match(word):
            kinds[member.group(1)] = None
        elif verb := _COMMAND.match(word):
            commands[verb.group(1)] = None
        elif _PATH.match(word):
            paths[word] = None
    return Names(kinds=list(kinds), paths=list(paths), commands=list(commands))


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Known:
    """What exists.

    Attributes:
        kinds: the names of ``brief.Kind``.
        commands: the names of the ``pitboss`` commands.
        tree: the directory the file paths are looked up from.
    """

    kinds: AbstractSet[str]
    commands: AbstractSet[str]
    tree: pathlib.Path


def missing_line(ticket: str, body: str, known: Known) -> str:
    """The line naming each name of the Done-when that does not exist.

    Args:
        ticket: the ticket, ``owner/repo#N``.
        body: the ticket's text.
        known: what exists.

    Returns:
        The line, or "" when every name exists or there are none.
    """
    names = names_in(done_when(body))
    missing = [
        *(f"brief.Kind.{each}" for each in names.kinds if each not in known.kinds),
        *(f"file {each}" for each in names.paths if not (known.tree / each).exists()),
        *(
            f"command pitboss {each}"
            for each in names.commands
            if each not in known.commands
        ),
    ]
    if not missing:
        return ""
    return (
        f"{LABEL}: {ticket}: the Done-when names what does not exist:"
        f" {', '.join(missing)}"
    )
