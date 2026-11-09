"""A numbered Plan row has a command, a read or a CI pointer (keyword: plan-pointer).

Found in pitboss#315 (pitboss#317): a Plan of four rows, each a file name and
nothing else, passed ``lint pr-body`` and ``plan-check``, and only a reviewer saw
that no row said what would be run, read or looked up in CI. ``plan-pointer`` is
the finding for each numbered row (``1. ...``) that has none of the three:

* a command: a backticked span that starts with a program (``rg -n x``,
  ``pitboss impact y``, ``./run``, after any ``NAME=value``), or a row that starts
  with ``$ ``;
* an exact read: a backticked file (``src/a.py``) and a word that says what it
  shows (``shows``, ``prints``, ``says``, ``lists``, ``holds``, ``names`` and the
  like);
* a CI pointer: a workflow file and a job, step or greppable string
  (``cipointer``).

A disposition line (``file:line: edited``) is no row. The module reads no file:
the Plan section is given.
"""

import re
from typing import Sequence

from . import cipointer, impactcheck, planrowtext

CHECK = "plan-pointer"
PROGRAMS = frozenset(
    "awk bash bats cat cd coverage curl diff echo env find gh git grep head jq ls make"
    " mypy node nox npm pip pitboss pytest python python3 rg sed sh sha256sum sort"
    " stolid tail test uv uvx virtue wc black flake8 time timeout".split()
)
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=\S*$")
FILE = re.compile(r"^[\w./-]*\w\.\w+$|^[\w.-]+/[\w./-]+$")
READS = re.compile(
    r"\b(?:shows?|showing|prints?|printing|says?|saying|lists?|listing|holds?"
    r"|contains?|names?|states?|gives?)\b",
    re.IGNORECASE,
)
MESSAGE = (
    "{check}: Plan row {number} has no command, exact read or CI pointer: give the"
    " command in backticks, a file in backticks with what it shows, or the CI"
    " pointer (workflow, job or step, greppable string)"
)


def _is_command(span: str) -> bool:
    words = span.split()
    while words and ASSIGNMENT.match(words[0]):
        words = words[1:]
    if not words:
        return False
    first = words[0]
    return first in PROGRAMS or first.startswith("./")


def _is_read(text: str) -> bool:
    files = [each for each in planrowtext.spans(text) if FILE.match(each)]
    # what it shows: a word of the row outside its backticks
    outside = planrowtext.SPAN.sub(" ", text)
    return bool(files) and READS.search(outside) is not None


def has_pointer(text: str) -> bool:
    """Whether a Plan row has a command, an exact read or a CI pointer.

    Args:
        text: the row's text, without its number.

    Returns:
        True when it has any of the three.
    """
    return (
        text.startswith("$ ")
        or any(_is_command(each) for each in planrowtext.spans(text))
        or _is_read(text)
        or bool(cipointer.read(text))
    )


def lacking(section: str) -> Sequence[int]:
    """The numbers of the numbered rows with no command, read or CI pointer.

    Args:
        section: the Plan section.

    Returns:
        The numbers, in order; a disposition line is no row.
    """
    return [
        number
        for number, text in planrowtext.rows(section).items()
        if not impactcheck.DISPOSITION.match(text) and not has_pointer(text)
    ]


def findings(section: str) -> Sequence[str]:
    """The findings for the Plan rows with no command, read or CI pointer.

    Args:
        section: the Plan section.

    Returns:
        One finding for each such numbered row, starting with ``plan-pointer:``.
    """
    return [MESSAGE.format(number=number, check=CHECK) for number in lacking(section)]
