"""Assertions about the words of a text, one call for several words."""

from typing import Protocol

from hamcrest import assert_that, equal_to

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


class Exited(Protocol):
    """What ran and ended with an exit code."""

    @property
    def code(self) -> object:
        """The exit code.

        Returns:
            The value.
        """


def exits(done: Exited, code: int) -> None:
    """Require a command's exit code.

    Args:
        done: what the command did.
        code: the exit code it must end with.
    """
    assert_that(done.code, equal_to(code))


class Ended(Exited, Protocol):
    """What ran, with its standard output."""

    @property
    def out(self) -> str:
        """The standard output.

        Returns:
            The value.
        """


def ended(done: Ended, code: int, out: str) -> None:
    """Require a command's exit code and its whole standard output.

    Args:
        done: what the command did.
        code: the exit code it must end with.
        out: all it must print.
    """
    assert_that((done.code, done.out), equal_to((code, out)))


class Failed(Exited, Protocol):
    """What ran, with its standard error."""

    @property
    def err(self) -> str:
        """The standard error.

        Returns:
            The value.
        """


def errs(done: Failed, code: int, *words: str) -> None:
    """Require a command's exit code and words of its standard error.

    Args:
        done: what the command did.
        code: the exit code it must end with.
        *words: what its standard error must hold.
    """
    exits(done, code)
    says(done.err, *words)


def outs(done: Ended, code: int, *words: str) -> None:
    """Require a command's exit code and words of its standard output.

    Args:
        done: what the command did.
        code: the exit code it must end with.
        *words: what its standard output must hold.
    """
    exits(done, code)
    says(done.out, *words)
