"""The check of a Plan's Impact list (keyword: impact-list, pitboss#320).

A Plan row ``pitboss impact PHRASE...`` is an Impact command: ``pitboss
plan-check`` runs the search itself, at the PR's head (``--head``), and holds the
Plan to its output. Every hit needs a disposition line in the Plan,
``file:line: edited`` or ``file:line: not edited`` with the reason after it, and
every line the Plan
cites that way must be a hit of some Impact command at that head, so a line
number that moved, or a statement a hand-typed list missed, is a finding of the
Plan and not of a review rounds later. The module reads no file: the hits are
given.
"""

import dataclasses
import posixpath
import re
import shlex
from typing import Mapping, Sequence

from . import impact

CHECK = "impact-list"
DISPOSITION = re.compile(
    r"^\s*(?:[-*]\s+)?(?P<path>[^\s:]+):(?P<line>\d+):\s+(?:not edited|edited)\b"
)
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
PROGRAM = ("pitboss", "impact")
OPERATORS = re.compile(r"^[();<>|&]+$")
SHELL_PROBLEM = (
    "an Impact command takes no pipe, redirect or list of commands: the Plan"
    " cites its whole output"
)
RAW = re.compile(r"(^|[\s/])pitboss\s+impact\b")
SPELLING_PROBLEM = (
    "an Impact command is read only as `pitboss impact`, behind `uvx` (with"
    " `--from DIR` or `--no-cache`) or `python -m`, after `NAME=value`: write it so"
)
WORD_PROBLEM = "an Impact command needs a phrase with a word"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Row:
    """A Plan row that is an Impact command.

    Attributes:
        phrases: the phrases it searches for.
        problem: why it cannot be run as the check runs it, empty when it can.
    """

    phrases: Sequence[str]
    problem: str = ""


def _words(command: str) -> Sequence[str] | None:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def parse(command: str) -> Row | None:
    """Whether a Plan row is an Impact command, and what it searches for.

    The program is ``pitboss impact``, behind ``uvx``, ``uvx --from DIR`` or
    ``python -m``, and after variable assignments (``PYTHONPATH=src``).

    Any other spelling of it (``uv run``, a path, ``env``, ``cd && ...``) is a
    row with a problem, not a row for ``sh``: the check never runs a launcher.

    Args:
        command: the row's command line.

    Returns:
        None for any other row; else its phrases, or the problem that keeps the
        check from running it as written (a pipe or a redirect after it, which
        would cut the list the Plan cites, no phrase, or a spelling it does not
        read).
    """
    words = _words(command)
    if words is None:
        spelled = RAW.search(command) is not None
        return Row(phrases=[], problem=SPELLING_PROBLEM) if spelled else None
    row = _read(list(words))
    if row is None and _names_program(words):
        return Row(phrases=[], problem=SPELLING_PROBLEM)
    return row


def _names_program(words: Sequence[str]) -> bool:
    programs = [posixpath.basename(each) for each in words]
    return PROGRAM in set(zip(programs, words[1:]))


def _read(words: list[str]) -> Row | None:
    while words and ASSIGNMENT.match(words[0]):
        words = words[1:]
    if words[:1] == ["uvx"]:
        words = _after_options(words[1:])
    elif words[:1] in (["python"], ["python3"]) and words[1:2] == ["-m"]:
        words = words[2:]
    if tuple(words[:2]) != PROGRAM:
        return None
    return _row(words[2:])


def _after_options(words: Sequence[str]) -> list[str]:
    # uvx options: --from takes a value, the others (--no-cache) none
    rest = list(words)
    while rest and rest[0].startswith("--"):
        rest = rest[2:] if rest[0] == "--from" else rest[1:]
    return rest


def _row(phrases: Sequence[str]) -> Row:
    if any(OPERATORS.match(each) for each in phrases):
        return Row(phrases=[], problem=SHELL_PROBLEM)
    if not phrases or not all(each.split() for each in phrases):
        return Row(phrases=[], problem=WORD_PROBLEM)
    return Row(phrases=phrases)


def dispositions(section: str) -> Mapping[tuple[str, int], int]:
    """The lines of a Plan section that dispose of a hit.

    Args:
        section: the Plan section.

    Returns:
        For each ``(file, line)`` a disposition line cites, the number of the
        Plan line that does (the first one).
    """
    found: dict[tuple[str, int], int] = {}
    for number, line in enumerate(section.splitlines(), 1):
        matched = DISPOSITION.match(line)
        if matched:
            path = matched["path"].removeprefix("./")
            found.setdefault((path, int(matched["line"])), number)
    return found


def _nearby(hits: Sequence[impact.Hit], path: str) -> str:
    lines = sorted({each.line for each in hits if each.path == path})
    if not lines:
        return f"{path} has no hit"
    return f"{path} has hits at line {', '.join(str(each) for each in lines)}"


def findings(hits: Sequence[impact.Hit], section: str) -> Sequence[str]:
    """What the Plan lacks or cites wrongly, against the hits at the head.

    Args:
        hits: the hits of every Impact command of the Plan.
        section: the Plan section.

    Returns:
        A finding for each hit with no disposition line, then one for each
        disposition line that cites a line that is not a hit.
    """
    cited = dispositions(section)
    present = {(each.path, each.line): each for each in hits}
    missing = [
        f"{CHECK}: {each.path}:{each.line} has no disposition line"
        f" ({each.path}:{each.line}: edited, or not edited and why): {each.text}"
        for key, each in present.items()
        if key not in cited
    ]
    stale = [
        f"{CHECK}: Plan line {number} cites {path}:{line}, which is not a hit at"
        f" this head ({_nearby(hits, path)})"
        for (path, line), number in cited.items()
        if (path, line) not in present
    ]
    return [*missing, *stale]
