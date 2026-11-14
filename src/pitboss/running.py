"""Running commands: the one seam between pitboss and the machine.

Commands get gather's runners, which log, raise ``CalledProcessError`` on
failure, and (``run`` only) do nothing in a dry run; tests pass fakes.
"""

import dataclasses
from typing import Callable, Protocol, Sequence


class Output(Protocol):
    """What a finished process gives back."""

    @property
    def stdout(self) -> str:
        """The process's standard output.

        Returns:
            The output.
        """


class Run(Protocol):
    """Runs a command line, raising ``CalledProcessError`` when it fails."""

    def __call__(self, cmdargs: Sequence[str], /) -> Output:
        """Run a command.

        Args:
            cmdargs: the command line.

        Returns:
            The finished process.
        """


class KeywordRun(Protocol):
    """Runs a command line and takes the keywords ``safe_run`` takes."""

    def __call__(
        self, cmdargs: Sequence[str], /, *args: object, **kwargs: object
    ) -> Output:
        """Run a command.

        Args:
            cmdargs: the command line.
            *args: its other positional arguments.
            **kwargs: its keywords (``check=True``, ``cwd=...``).

        Returns:
            The finished process.
        """


def git(run: Run, directory: object, *arguments: str) -> str:
    """Run git in a directory.

    Args:
        run: the runner.
        directory: the checkout.
        *arguments: git's arguments.

    Returns:
        git's output.
    """
    return run(["git", "-C", str(directory), *arguments]).stdout


def changed_files(run: Run, directory: object, *options: str) -> int:
    """Count the files ``git status`` lists in a checkout.

    Args:
        run: the runner.
        directory: the checkout.
        *options: more options of ``git status``.

    Returns:
        The count.
    """
    return len(git(run, directory, "status", "--porcelain", *options).splitlines())


def through(
    run: KeywordRun,
    read: Callable[[Sequence[str]], Output],
    cmdargs: Sequence[str],
    *args: object,
    **kwargs: object,
) -> Output:
    """Run a command; a plain ``gh api <path>`` read goes through ``read``.

    Args:
        run: the runner any other command goes through.
        read: what a plain read goes through (the memo, the tries).
        cmdargs: the command line.
        *args: its other positional arguments.
        **kwargs: its keywords.

    Returns:
        The finished process.
    """
    words = list(cmdargs)
    if words[:2] != ["gh", "api"] or len(words) != 3 or args or kwargs:
        return run(cmdargs, *args, **kwargs)
    return read(words)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class GitHub:
    """GitHub's REST API, through ``gh api``.

    Attributes:
        run: the runner reads go through.
        mutate: the runner changes go through (a dry run unless asked).
    """

    run: Run
    mutate: Run


def read_only(run: Run) -> GitHub:
    """The API for a command that only reads (it never changes GitHub).

    Args:
        run: the runner reads go through.

    Returns:
        The API, whose changes go through the same runner.
    """
    return GitHub(run=run, mutate=run)
