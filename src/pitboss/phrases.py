"""Banned phrases: the phrase files, their small pattern language, and the search.

A phrase file has one phrase on each line, four fields separated by tabs: a
label, a pattern, an example the pattern matches, and what to do instead. A
line that is blank or starts with ``#`` is not a phrase.

The pattern language is a sequence of atoms, searched anywhere in a line
without regard to case. An atom is a character, ``\\s``, ``\\d``, ``\\w``,
``\\b`` (a word edge), ``\\<c>`` (the character c), or a class ``[...]`` /
``[^...]`` of characters and the three escapes. ``?``, ``+`` and ``*`` may
follow an atom other than ``\\b``. There is no group and no alternation: an
alternative is a line of its own.
"""

import dataclasses
import importlib.resources
import pathlib
import re
from typing import Sequence

FIELDS = 4
CLASS_ESCAPES = "sdw"
ATOM_ESCAPES = CLASS_ESCAPES + "b"
QUANTIFIERS = "?+*"
REFUSED = "()|"
SHOWN = 120


class PhraseError(Exception):
    """A pattern or a phrase file that is not well formed."""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Phrase:
    """One banned phrase.

    Attributes:
        label: the class of mistake.
        pattern: the pattern, as written.
        example: a text the pattern matches.
        instead: what to do instead.
        regex: the compiled pattern.
    """

    label: str
    pattern: str
    example: str
    instead: str
    regex: re.Pattern[str]


TOKEN = re.compile(r"\[[^\]]*\]|\\.?|.", re.DOTALL)
PIECE = re.compile(r"\\.?|.", re.DOTALL)


def _class_piece(piece: str) -> str:
    if len(piece) == 2:
        return piece if piece[1] in CLASS_ESCAPES else re.escape(piece[1])
    return re.escape(piece)


def _class(token: str) -> str:
    body = token[1:-1]
    negated = body.startswith("^")
    if negated:
        body = body[1:]
    if not body:
        raise PhraseError(f"{token}: a class holds no character")
    pieces = "".join(_class_piece(each) for each in PIECE.findall(body))
    return f"[{'^' if negated else ''}{pieces}]"


def _atom(token: str) -> tuple[str, bool]:
    if token in REFUSED:
        raise PhraseError(
            f"{token!r} is a group or an alternation, which the language has"
            " not: give each alternative a line"
        )
    if token == "[":
        raise PhraseError("a class is not closed")
    if token.startswith("["):
        return _class(token), True
    if len(token) == 2 and token.startswith("\\"):
        if token[1] in ATOM_ESCAPES:
            return token, token[1] != "b"
        return re.escape(token[1]), True
    return re.escape(token), True


def compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compile a pattern of the phrase language.

    Args:
        pattern: the pattern.

    Returns:
        The case-insensitive regular expression that searches for it.

    Raises:
        PhraseError: when the pattern is empty or uses what the language has not.
    """
    if not pattern:
        raise PhraseError("a pattern is empty")
    parts: list[str] = []
    repeatable = False
    for token in TOKEN.findall(pattern):
        if token in QUANTIFIERS and parts and repeatable:
            parts[-1] += token
            repeatable = False
            continue
        if token in QUANTIFIERS:
            raise PhraseError(f"{token!r} follows no atom or a word edge")
        text, repeatable = _atom(token)
        parts.append(text)
    return re.compile("".join(parts), re.IGNORECASE)


def _phrase(line: str, source: str) -> Phrase:
    fields = line.split("\t")
    if len(fields) != FIELDS:
        raise PhraseError(
            f"{source}: a phrase has {FIELDS} fields separated by tabs, this"
            f" line has {len(fields)}"
        )
    label, pattern, example, instead = fields
    try:
        regex = compile_pattern(pattern)
    except PhraseError as error:
        raise PhraseError(f"{source}: {pattern}: {error}") from error
    if not regex.search(example):
        raise PhraseError(
            f"{source}: the example {example!r} does not match its pattern"
            f" {pattern!r}"
        )
    return Phrase(
        label=label, pattern=pattern, example=example, instead=instead, regex=regex
    )


def parse(text: str, source: str) -> Sequence[Phrase]:
    """Read the phrases of a phrase file's text.

    Args:
        text: the file's text.
        source: its name, for the errors.

    Returns:
        The phrases; a line that is not a phrase, or whose example does not
        match its own pattern, is a ``PhraseError`` naming its line.
    """
    return [
        _phrase(line, f"{source}:{number}")
        for number, line in enumerate(text.split("\n"), 1)
        if line.strip() and not line.startswith("#")
    ]


def default_text() -> str:
    """The text of the phrase file pitboss ships.

    Returns:
        The text.
    """
    return (importlib.resources.files("pitboss") / "phrases.tsv").read_text(
        encoding="utf-8"
    )


def load(path: pathlib.Path) -> Sequence[Phrase]:
    """Read a project's phrase file.

    Args:
        path: the file.

    Returns:
        The phrases.

    Raises:
        PhraseError: when the file cannot be read or is not well formed.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PhraseError(f"{path}: {error.strerror}") from error
    return parse(text, str(path))


def _shown(line: str) -> str:
    shown = line.strip()
    return shown if len(shown) <= SHOWN else shown[: SHOWN - 3] + "..."


def findings(text: str, name: str, phrases: Sequence[Phrase]) -> Sequence[str]:
    """Find the banned phrases in a text, one finding for each phrase and line.

    Args:
        text: the text.
        name: what to call it in a finding.
        phrases: the phrases.

    Returns:
        The findings, in line order and then in the phrases' order.
    """
    found = []
    for number, line in enumerate(text.split("\n"), 1):
        for banned in phrases:
            match = banned.regex.search(line)
            if match:
                found.append(
                    f'{name}:{number}: {banned.label}: the line "{_shown(line)}"'
                    f' holds the phrase "{match.group(0)}", which is refused:'
                    f" {banned.instead}"
                )
    return found
