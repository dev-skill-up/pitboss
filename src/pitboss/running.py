"""Running commands: the one seam between pitboss and the machine.

Commands get gather's runners, which log, raise ``CalledProcessError`` on
failure, and (``run`` only) do nothing in a dry run; tests pass fakes.
"""

from typing import Protocol, Sequence


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
