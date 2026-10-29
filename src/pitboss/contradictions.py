"""Contradictions: a rule stated two ways in the guideline files.

A pairs file has one pair on each line, five fields separated by tabs: a
pattern for one side, a pattern for the other, an example of each side and what
to do instead. A line that is blank or starts with ``#`` is not a pair. The
patterns are those of the phrase language (``phrases``), searched in a line
without regard to case, after its code spans (text between backticks) are
removed. A pair is found when one side matches a line of one of the files and
the other side a line of one of the files, the same file or the same line
included.
"""

import dataclasses
import pathlib
import re
from typing import Sequence

from . import phrases

FIELDS = 5
CODE_SPAN = re.compile(r"`[^`]*`")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Pair:
    """Two sentences no guideline files may hold together.

    Attributes:
        first: the pattern of one side, as written.
        second: the pattern of the other side, as written.
        first_regex: the compiled first pattern.
        second_regex: the compiled second pattern.
        instead: what to do instead.
    """

    first: str
    second: str
    first_regex: re.Pattern[str]
    second_regex: re.Pattern[str]
    instead: str


def _compile(pattern: str, example: str, source: str) -> re.Pattern[str]:
    try:
        regex = phrases.compile_pattern(pattern)
    except phrases.PhraseError as error:
        raise phrases.PhraseError(f"{source}: {pattern}: {error}") from error
    if not regex.search(strip_code(example)):
        raise phrases.PhraseError(
            f"{source}: the example {example!r} does not match its pattern"
            f" {pattern!r}"
        )
    return regex


def strip_code(line: str) -> str:
    """Remove the code spans of a line.

    Args:
        line: the line.

    Returns:
        The line without the text between backticks.
    """
    return CODE_SPAN.sub("", line)


def _pair(line: str, source: str) -> Pair:
    fields = line.split("\t")
    if len(fields) != FIELDS:
        raise phrases.PhraseError(
            f"{source}: a pair has {FIELDS} fields separated by tabs, this"
            f" line has {len(fields)}"
        )
    first, second, first_example, second_example, instead = fields
    return Pair(
        first=first,
        second=second,
        first_regex=_compile(first, first_example, source),
        second_regex=_compile(second, second_example, source),
        instead=instead,
    )


def parse(text: str, source: str) -> Sequence[Pair]:
    """Read the pairs of a pairs file's text.

    Args:
        text: the file's text.
        source: its name, for the errors.

    Returns:
        The pairs; a line that is not a pair, or whose example does not match
        its own pattern, is a ``PhraseError`` naming its line.
    """
    return phrases.parse_rows(text, source, _pair)


def default_text() -> str:
    """The text of the pairs file pitboss ships.

    Returns:
        The text.
    """
    return phrases.shipped_text("contradictions.tsv")


def load(path: pathlib.Path) -> Sequence[Pair]:
    """Read a project's pairs file.

    Args:
        path: the file.

    Returns:
        The pairs; a file that cannot be read or is not well formed is a
        ``PhraseError``.
    """
    return parse(phrases.read_text(path), str(path))


def _first_line(
    files: Sequence[tuple[str, str]], regex: re.Pattern[str]
) -> tuple[str, int, str] | None:
    for name, body in files:
        for number, line in enumerate(body.split("\n"), 1):
            if regex.search(strip_code(line)):
                return name, number, line.strip()
    return None


def _shown(line: str) -> str:
    return line if len(line) <= phrases.SHOWN else line[: phrases.SHOWN - 3] + "..."


def _side(mine: tuple[str, int, str], other: tuple[str, int, str], advice: str) -> str:
    return (
        f'{mine[0]}:{mine[1]}: contradiction: the line "{_shown(mine[2])}"'
        f" is one side of a pair with {other[0]}:{other[1]}: {advice}"
    )


def findings(
    files: Sequence[tuple[str, str]], candidates: Sequence[Pair]
) -> Sequence[str]:
    """Find the pairs whose two sides the files hold.

    Args:
        files: each file's name and text.
        candidates: the pairs.

    Returns:
        Two lines for each pair found, one for each side, the first line of
        each side; each names the other side's place and what to do instead.
    """
    found: list[str] = []
    for each in candidates:
        left = _first_line(files, each.first_regex)
        right = _first_line(files, each.second_regex)
        if left is not None and right is not None:
            found.append(_side(left, right, each.instead))
            found.append(_side(right, left, each.instead))
    return found
