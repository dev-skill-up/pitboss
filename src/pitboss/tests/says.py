"""Assertions about the words of a text, one call for several words."""

from .briefmake import has_all, has_none


def says(text: str, *words: str) -> None:
    """Require every word to be in a text.

    Args:
        text: what a command printed.
        *words: the pieces of text that must be in it.
    """
    has_all(text, words)


def lacks(text: str, *words: str) -> None:
    """Require every word to be absent from a text.

    Args:
        text: what a command printed.
        *words: the pieces of text that must not be in it.
    """
    has_none(text, words)
