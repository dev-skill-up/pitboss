"""Texts cut at a separator, and lines picked by their start."""

import re
from typing import Iterable, Sequence


def split_at(text: str, separator: str) -> tuple[str, str]:
    """A text cut at the first separator.

    Args:
        text: the text.
        separator: where it is cut.

    Returns:
        What comes before the separator and what comes after it; the whole text
        and "" when the separator is not in it.
    """
    before, _, after = text.partition(separator)
    return before, after


def split_last(text: str, separator: str) -> tuple[str, str]:
    """A text cut at the last separator.

    Args:
        text: the text.
        separator: where it is cut.

    Returns:
        What comes before the separator and what comes after it; "" and the
        whole text when the separator is not in it.
    """
    before, _, after = text.rpartition(separator)
    return before, after


def starting(lines: Iterable[str], prefix: str) -> Sequence[str]:
    """The lines that start with a prefix.

    Args:
        lines: the lines.
        prefix: the start.

    Returns:
        Those lines, in order.
    """
    return [line for line in lines if line.startswith(prefix)]


def heads(text: str, start: str, separator: str) -> bool:
    """Whether a text is a start, or the start and a separator then more.

    Args:
        text: the text.
        start: the start.
        separator: what follows the start when there is more.

    Returns:
        True when it is.
    """
    return text == start or text.startswith(start + separator)


def mentions_any(text: str, words: Iterable[str]) -> bool:
    """Whether a text holds any of some words.

    Args:
        text: the text.
        words: the words.

    Returns:
        True when one is in it.
    """
    return any(word in text for word in words)


def section_after(text: str, found: re.Match[str], heading: re.Pattern[str]) -> str:
    """The text after a match, up to the next heading.

    Args:
        text: the text.
        found: the match the section starts after.
        heading: the start of the next section.

    Returns:
        The section's text; the rest of the text when no heading follows.
    """
    rest = text[found.end() :]
    after = heading.search(rest)
    return rest[: after.start()] if after else rest


def hyphenated(name: str) -> str:
    """A member's name as it is typed: lower case, with hyphens.

    Args:
        name: the name (``NOT_LANDED``).

    Returns:
        The word (``not-landed``).
    """
    return name.lower().replace("_", "-")


def having(lines: Iterable[str], word: str) -> Sequence[str]:
    """The lines that hold a word.

    Args:
        lines: the lines.
        word: the word.

    Returns:
        Those lines, in order.
    """
    return [line for line in lines if word in line]
