"""The command line parser: options before git's arguments (keyword: argparse-order).

``pitboss push CONFIG --now X --no-dry-run origin branch`` has a positional list
(``git_arguments``) after options. argparse before 3.13 (3.12.3 shown by
pitboss#70) matches both positionals at the first positional it sees, so the
list is empty and the words after the options are "unrecognized arguments". The
intermixed parse reads the options first and the positionals after, on every
version, so a subcommand is parsed with it.
"""

import argparse
import contextlib
from collections.abc import Iterator, Sequence

from gather import commands as gather_commands

from . import ENTRY_DATA


@contextlib.contextmanager
def intermixing(parser: "IntermixedParser") -> Iterator[None]:
    """Mark a parser as inside its intermixed parse.

    Args:
        parser: the parser.

    Yields:
        Nothing, while the mark is set.
    """
    parser.reading_intermixed = True
    try:
        yield
    finally:
        parser.reading_intermixed = False


# argparse builds a subcommand's parser from the class of the parser that holds it,
# so the class is the one place the parse can change.
class IntermixedParser(argparse.ArgumentParser):  # noqa: SLD504,SLD401
    """A parser whose subcommands accept options among their positionals.

    Attributes:
        reading_intermixed: set while the intermixed parse is running.
    """

    reading_intermixed = False

    def parse_known_args(  # type: ignore[override]
        self,
        args: Sequence[str] | None = None,
        namespace: argparse.Namespace | None = None,
    ) -> tuple[argparse.Namespace, Sequence[str]]:  # noqa: SLD803
        """Parse a subcommand's arguments with options among the positionals.

        The parser that holds the subcommands is parsed as argparse does: the
        intermixed parse takes no subcommands.

        Args:
            args: the words to parse.
            namespace: where to put the values.

        Returns:
            The namespace and the words left over.
        """
        if self.reading_intermixed or self._subparsers is not None:
            return super().parse_known_args(args, namespace)
        with intermixing(self):
            return self.parse_known_intermixed_args(args, namespace)


def make_parser() -> argparse.ArgumentParser:
    """The command line parser of every pitboss command.

    Returns:
        The parser.
    """
    made: argparse.ArgumentParser = gather_commands.set_parser(
        collected=ENTRY_DATA.collector.collect(), parser=IntermixedParser()
    )
    return made
