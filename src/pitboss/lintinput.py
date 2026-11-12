"""What ``lint`` reads: files, phrase files and pair files (keyword: lint-input)."""

import argparse
import pathlib
import sys
from typing import Callable, NoReturn, Sequence, TypeVar

from . import contradictions, phrases

USAGE_ERROR = 2
_Rule = TypeVar("_Rule")


def fail(message: str) -> NoReturn:
    """Say why the command cannot go on; it never returns, it ends the command.

    Args:
        message: the reason, printed on standard error.

    Raises:
        SystemExit: always, with status 2.
    """
    print(message, file=sys.stderr)
    raise SystemExit(USAGE_ERROR)


def shipped_and_given(
    shipped: Sequence[_Rule],
    given: Sequence[str] | None,
    load: Callable[[pathlib.Path], Sequence[_Rule]],
) -> Sequence[_Rule]:
    """The rules pitboss ships and those of the files the user gave.

    Args:
        shipped: the rules pitboss ships.
        given: the paths of rule files, or none.
        load: reads the rules of a file.

    Returns:
        The shipped rules, then the given ones.
    """
    found = list(shipped)
    try:
        for path in given or ():
            found.extend(load(pathlib.Path(path)))
    except phrases.PhraseError as error:
        fail(str(error))
    return found


def phrase_rules(args: argparse.Namespace) -> Sequence[phrases.Phrase]:
    """The banned phrases: the shipped file's and the files given.

    Args:
        args: the parsed arguments.

    Returns:
        The phrases.
    """
    shipped = (
        []
        if args.no_default_phrases
        else phrases.parse(phrases.default_text(), "default phrases")
    )
    return shipped_and_given(shipped, args.phrases, phrases.load)


def pair_rules(args: argparse.Namespace) -> Sequence[contradictions.Pair]:
    """The pairs of contradicting texts: the shipped file's and the files given.

    Args:
        args: the parsed arguments.

    Returns:
        The pairs.
    """
    shipped = (
        []
        if args.no_default_pairs
        else contradictions.parse(contradictions.default_text(), "default pairs")
    )
    return shipped_and_given(shipped, args.pairs, contradictions.load)


def read(name: str) -> str:
    """Read a text file.

    Args:
        name: the file's path.

    Returns:
        Its text; a file that cannot be read ends the command with status 2.
    """
    try:
        return phrases.read_text(pathlib.Path(name))
    except phrases.PhraseError as error:
        fail(str(error))


def read_files(args: argparse.Namespace) -> Sequence[tuple[str, str]]:
    """Read the files the command was given.

    Args:
        args: the parsed arguments.

    Returns:
        Each file's name and text.
    """
    return [(name, read(name)) for name in args.files]


def finish(refused: Sequence[str], ok: str) -> None:
    """Print the refusals and exit 1, or print the ok line.

    Args:
        refused: the findings, one line each.
        ok: the line printed when there is none.

    Raises:
        SystemExit: 1 when there is a finding.
    """
    for each in refused:
        print(each)
    if refused:
        raise SystemExit(1)
    print(ok)


def exactly(args: argparse.Namespace, wanted: Sequence[str]) -> Sequence[str]:
    """The texts of the files a check takes, each named in a refusal.

    Args:
        args: the parsed arguments, with ``kind`` and ``files``.
        wanted: what the check takes, one word for each file.

    Returns:
        The texts, in the order given.
    """
    if len(args.files) != len(wanted):
        fail(f"{args.kind} checks {', '.join(wanted)}, not {len(args.files)}")
    return [read(each) for each in args.files]
