"""Where a command's configuration comes from (keyword: default-config).

Every command that takes one has ``--config NAME``. The old form, the
configuration as the command's first word, works for one published version
(the overlap rule); until pitboss#310 removes it, that word is the
configuration only when ``configsearch.names_a_config`` says so, and any other
first word is the command's own (git's argument, the ticket, the slot).
"""

import argparse
import functools
import sys
from typing import Iterable, Mapping, NoReturn, Protocol, Sequence, cast

from gather.api import Wrapper

from . import configfetch, configsearch
from .commandarguments import CONFIG_OPTION
from .running import Run

DEPRECATED = (
    "DEPRECATED: the configuration as the first word of `pitboss {command}`"
    " will be removed; give it as `--config NAME` (pitboss#310)"
)


def _refuse(command: str, word: str) -> NoReturn:
    print(
        f"pitboss {command}: unexpected argument {word}"
        " (the configuration is given as --config NAME)",
        file=sys.stderr,
    )
    raise SystemExit(2)


def _can_take(args: argparse.Namespace, destination: str | None) -> bool:
    # a list or an optional word takes one more; a required word is already set
    if destination is None:
        return False
    return not isinstance(getattr(args, destination), str)


def _give_back(args: argparse.Namespace, destination: str, word: str) -> None:
    held = getattr(args, destination)
    setattr(args, destination, word if held is None else [word, *held])


def _output(run: Run, command: Sequence[str]) -> str:
    return run(command).stdout


def found_or_fetched(args: argparse.Namespace) -> str:
    """The configuration of a command that was given none (keyword: fetched-config).

    ``$PITBOSS_CONFIG``, then the search, then ``<repository>.toml`` fetched
    from the notes repository, which a fresh container needs: it has the
    checkout and nothing else.

    Args:
        args: the parsed arguments.

    Returns:
        A path, or a name (see ``locate`` of ``configfile``); when there is
        none, ``configfetch.fetch`` raises ``FileNotFoundError`` saying where
        the search looked and why the fetch failed.
    """
    try:
        return configsearch.named(args)
    except FileNotFoundError as missing:
        start = configsearch.working_directory(args)
        name = configsearch.repository_name(start, configsearch.ceilings(args.env))
        read = functools.partial(_output, args.safe_run)
        return str(configfetch.fetch(read, args.env, name, missing))


def settle(args: argparse.Namespace, destination: str | None) -> None:
    """Decide the configuration, and give the first word back when it is not one.

    The positional configuration is optional and first, so argparse gives it
    the first word of every command. ``--config`` wins, and then no word is
    read as the configuration; else the first word is the old configuration
    when it names one or when the command has nowhere else to put it. With
    none given, the configuration is the one ``found_or_fetched`` gives.

    Args:
        args: the parsed arguments; ``config`` is the first word (or None) and
            ``config_option`` is ``--config``.
        destination: the argument that takes the command's next positional word.
    """
    _read_word(args, destination)
    if args.config is None:
        args.config = found_or_fetched(args)


def _read_word(args: argparse.Namespace, destination: str | None) -> None:
    word, option = args.config, args.config_option
    command = args.__gather_name__
    if word is None:
        args.config = option
        return
    start = configsearch.working_directory(args)
    if option is None and (
        not _can_take(args, destination) or configsearch.names_a_config(word, start)
    ):
        # keyword: default-config: the old positional form, removed by pitboss#310
        print(DEPRECATED.format(command=command), file=sys.stderr)
        return
    if destination is None or not _can_take(args, destination):
        _refuse(command, word)
    _give_back(args, destination, word)
    args.config = option


def find_or_say(args: argparse.Namespace) -> None:
    """Find the configuration of ``lint`` or ``plan-check`` when none is given.

    ``$PITBOSS_CONFIG``, then the search, then the fetch by the repository's
    name (``configfetch``); one found is used as if it had been given. With
    none, the command keeps its generic forms and says on standard error every
    place it looked.

    Args:
        args: the parsed arguments, whose ``config`` is ``--config``.
    """
    if args.config is not None:
        return
    try:
        args.config = found_or_fetched(args)
    except FileNotFoundError as error:
        print(error, file=sys.stderr)


class Described(Protocol):
    """An argument of a registered command, as ``add_argument`` described it."""

    @property
    def args(self) -> Sequence[str]:
        """The names the argument is given as.

        Returns:
            The names (``config``, or ``--now``).
        """


def names_of(extra: object) -> Sequence[str]:
    """The first name of each argument a command was registered with.

    Args:
        extra: the arguments (``add_argument`` descriptions).

    Returns:
        The names (``config``, ``--now``).
    """
    listed = cast(Sequence[Described], extra)  # noqa: SLD203
    return [each.args[0] for each in listed]


def takes_config(extra: object) -> bool:
    """Whether a command's registered arguments hold the first-word configuration.

    Args:
        extra: the arguments the command was registered with.

    Returns:
        True when one is the positional ``config``.
    """
    return "config" in names_of(extra)


class Command(Protocol):
    """A command as ``gather`` calls it."""

    def __call__(self, *, args: argparse.Namespace) -> object:
        """Run the command.

        Args:
            args: the parsed arguments.

        Returns:
            Whatever the command returns.
        """


def _settling(run: Command, destination: str | None) -> Command:
    @functools.wraps(run)
    def settled(*, args: argparse.Namespace) -> object:
        settle(args, destination)
        return run(args=args)

    return settled


def _with_option(found: object) -> object:
    # the argument after the configuration is where a word that is not one goes
    wrapper = cast(Wrapper, found)  # noqa: SLD203
    if not takes_config(wrapper.extra):
        return wrapper
    listed = cast(Sequence[Described], wrapper.extra)  # noqa: SLD203
    words = [each.args[0] for each in listed if not each.args[0].startswith("-")]
    after = words[words.index("config") + 1 :]
    run = cast(Command, wrapper.original)  # noqa: SLD203
    return Wrapper(
        original=_settling(run, after[0] if after else None),
        extra=(*listed, CONFIG_OPTION),
    )


def with_option(
    collected: Mapping[str, Iterable[object]],
) -> Mapping[str, Sequence[object]]:
    """Give every command that takes the first-word configuration ``--config``.

    Args:
        collected: what ``ENTRY_DATA.collector.collect`` gives.

    Returns:
        The same commands, each such command with the option and the settling of
        its configuration (``settle``) run before it.
    """
    return {
        name: [_with_option(each) for each in wrappers]
        for name, wrappers in collected.items()
    }
