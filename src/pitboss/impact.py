"""The search that builds a Plan's Impact list (keyword: impact-list, pitboss#320).

``pitboss impact PHRASE...`` finds every statement about a behaviour in the
whole tree it runs in, at the head of that checkout, and prints each hit as
``file:line:text``, so the Plan cites a list a person did not type: a hand-built
list missed hits (a docstring, a markdown file, a wrapped sentence) and carried
line numbers that moved. A phrase is plain words: it matches without regard to
case, and its words are separated by any whitespace, a line break included, with
the marks that continue a wrapped sentence (a comment ``#``, a bullet or ``>``,
the closing and opening quotes of a string that is split over lines) allowed in
the break. The search walks the directory and not the index, so a file not yet
added is searched too. It leaves out ``.git``, the ``build`` and ``skill-zips``
directories of the root and the caches (``CACHES``); a file with a NUL byte is
binary and is not read.
"""

import dataclasses
import os
import pathlib
import re
from typing import Iterator, Sequence

ROOT_ONLY = frozenset({"build", "skill-zips"})
CACHES = frozenset(
    {
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".hypothesis",
        ".tox",
        ".nox",
    }
)
ALWAYS = frozenset({".git"}) | CACHES
# the marks a wrapped sentence carries from one line to the next
MARKS = "\"'#*/>|\\\\"
BREAK = rf"[{MARKS}]*\s[\s{MARKS}]*"


class PhraseError(ValueError):  # noqa: SLD504,SLD401
    """A phrase that cannot be searched."""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Hit:
    """A line where a phrase starts.

    Attributes:
        path: the file, relative to the root, with ``/`` between its parts.
        line: the line number, from 1.
        text: the line, without trailing whitespace.
    """

    path: str
    line: int
    text: str


def shown(hit: Hit) -> str:
    """The hit as ``pitboss impact`` prints it.

    Args:
        hit: the hit.

    Returns:
        ``file:line:text``.
    """
    return f"{hit.path}:{hit.line}:{hit.text}"


def expression(phrase: str) -> re.Pattern[str]:
    """The expression that finds a phrase.

    Args:
        phrase: plain words.

    Returns:
        The expression, case-insensitive, with a whitespace break between words.

    Raises:
        PhraseError: when the phrase has no word.
    """
    words = phrase.split()
    if not words:
        raise PhraseError("a phrase has no word")
    return re.compile(BREAK.join(re.escape(each) for each in words), re.IGNORECASE)


def _files(root: pathlib.Path) -> Iterator[pathlib.Path]:
    for here, names, files in os.walk(root):
        top = pathlib.Path(here) == root
        names[:] = sorted(
            each
            for each in names
            if each not in ALWAYS and not (top and each in ROOT_ONLY)
        )
        for entry in sorted(files):
            path = pathlib.Path(here) / entry
            if entry != ".git" and not path.is_symlink():
                yield path


def _line_numbers(text: str, expressions: Sequence[re.Pattern[str]]) -> Sequence[int]:
    found = {
        text.count("\n", 0, each.start()) + 1
        for found_in in expressions
        for each in found_in.finditer(text)
    }
    return sorted(found)


def _read(path: pathlib.Path) -> str:
    data = path.read_bytes()
    return "" if b"\0" in data else data.decode("utf-8", errors="replace")


def hits_in(root: pathlib.Path, phrases: Sequence[str]) -> Sequence[Hit]:
    """Every line of the tree where one of the phrases starts.

    Args:
        root: the checkout.
        phrases: the phrases.

    Returns:
        The hits, by file path and then line.
    """
    expressions = [expression(each) for each in phrases]
    found: list[Hit] = []
    for path in _files(root):
        text = _read(path)
        lines = text.split("\n")
        relative = path.relative_to(root).as_posix()
        found.extend(
            Hit(path=relative, line=number, text=lines[number - 1].rstrip())
            for number in _line_numbers(text, expressions)
        )
    return sorted(found, key=lambda each: (each.path, each.line))
