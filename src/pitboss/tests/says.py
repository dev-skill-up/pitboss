"""Assertions about the words of a text, one call for several words."""

from typing import Callable, Protocol, Sequence

from hamcrest import assert_that, contains_string, equal_to


def has_all(found: str, wanted: Sequence[str]) -> None:
    """Check that a text contains each wanted text.

    Args:
        found: the text.
        wanted: the texts it must contain.
    """
    for each in wanted:
        assert_that(found, contains_string(each))


def has_none(found: str, unwanted: Sequence[str]) -> None:
    """Check that a text contains none of the unwanted texts.

    Args:
        found: the text.
        unwanted: the texts it must not contain.
    """
    for each in unwanted:
        assert_that(each in found, equal_to(False))


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


class Printed(Protocol):
    """What ran, with its exit code and standard output."""

    @property
    def code(self) -> object:
        """The exit code.

        Returns:
            The value.
        """

    @property
    def out(self) -> str:
        """The standard output.

        Returns:
            The value.
        """


def ended(done: Printed, code: int, out: str) -> None:
    """Require a command's exit code and its whole standard output.

    Args:
        done: what the command did.
        code: the exit code it must end with.
        out: all it must print.
    """
    assert_that((done.code, done.out), equal_to((code, out)))


class Failed(Protocol):
    """What ran, with its exit code and standard error."""

    @property
    def code(self) -> object:
        """The exit code.

        Returns:
            The value.
        """

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


def outs(done: Printed, code: int, *words: str) -> None:
    """Require a command's exit code and words of its standard output.

    Args:
        done: what the command did.
        code: the exit code it must end with.
        *words: what its standard output must hold.
    """
    exits(done, code)
    says(done.out, *words)


def raises_with(error: type[Exception], words: str, call: Callable[[], object]) -> None:
    """Require a call to raise an error whose message holds the words.

    Args:
        error: the error it must raise.
        words: what the message must hold.
        call: the call.

    Raises:
        AssertionError: the call raised nothing.
    """
    try:
        call()
    except error as raised:
        assert_that(str(raised), contains_string(words))
        return
    raise AssertionError(f"no {error.__name__}")  # pragma: no cover


class Finished(Protocol):
    """What ran, with its exit code and both outputs."""

    @property
    def code(self) -> object:
        """The exit code.

        Returns:
            The value.
        """

    @property
    def out(self) -> str:
        """The standard output.

        Returns:
            The value.
        """

    @property
    def err(self) -> str:
        """The standard error.

        Returns:
            The value.
        """


def read_failed(done: Finished) -> None:
    """Require a command that ended on a failed read: status 1, nothing decided.

    Args:
        done: what the command did.
    """
    assert_that((done.code, done.out), equal_to((1, "")))
    says(done.err, "READ FAILED")
