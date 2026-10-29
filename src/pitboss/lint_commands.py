"""The ``lint`` command: checks of the texts agents write."""

import argparse
import pathlib
import sys
from typing import Callable, Mapping, Sequence, TypeVar

from gather.commands import add_argument

from . import ENTRY_DATA, contradictions, phrases

USAGE_ERROR = 2
_Rule = TypeVar("_Rule")


def _fail(message: str) -> SystemExit:
    print(message, file=sys.stderr)
    return SystemExit(USAGE_ERROR)


def _shipped_and_given(
    shipped: Sequence[_Rule],
    given: Sequence[str] | None,
    load: Callable[[pathlib.Path], Sequence[_Rule]],
) -> list[_Rule]:
    found = list(shipped)
    try:
        for path in given or ():
            found.extend(load(pathlib.Path(path)))
    except phrases.PhraseError as error:
        raise _fail(str(error)) from error
    return found


def _phrases(args: argparse.Namespace) -> list[phrases.Phrase]:
    shipped = (
        []
        if args.no_default_phrases
        else phrases.parse(phrases.default_text(), "default phrases")
    )
    return _shipped_and_given(shipped, args.phrases, phrases.load)


def _pairs(args: argparse.Namespace) -> list[contradictions.Pair]:
    shipped = (
        []
        if args.no_default_pairs
        else contradictions.parse(contradictions.default_text(), "default pairs")
    )
    return _shipped_and_given(shipped, args.pairs, contradictions.load)


def _read_files(args: argparse.Namespace) -> list[tuple[str, str]]:
    try:
        return [(name, phrases.read_text(pathlib.Path(name))) for name in args.files]
    except phrases.PhraseError as error:
        raise _fail(str(error)) from error


def _contradictions(args: argparse.Namespace) -> None:
    pairs = _pairs(args)
    refused = contradictions.findings(_read_files(args), pairs)
    for each in refused:
        print(each)
    if refused:
        raise SystemExit(1)
    print(f"ok: {len(pairs)} pairs")


def _text(args: argparse.Namespace) -> None:
    banned = _phrases(args)
    refused: list[str] = []
    for name, body in _read_files(args):
        refused.extend(phrases.findings(body, name, banned))
    for each in refused:
        print(each)
    if refused:
        raise SystemExit(1)
    print(f"ok: {len(banned)} phrases")


KINDS: Mapping[str, Callable[[argparse.Namespace], None]] = {
    "text": _text,
    "contradictions": _contradictions,
}


@ENTRY_DATA.register(
    add_argument("kind", choices=tuple(KINDS)),
    add_argument("files", nargs="+", help="the texts to check"),
    add_argument(
        "--phrases",
        action="append",
        default=None,
        help="a phrase file, added to the ones pitboss ships; give it more than once",
    ),
    add_argument(
        "--no-default-phrases",
        action="store_true",
        default=False,
        help="leave out the phrase file pitboss ships",
    ),
    add_argument(
        "--pairs",
        action="append",
        default=None,
        help="a pairs file for contradictions, added to the ones pitboss ships;"
        " give it more than once",
    ),
    add_argument(
        "--no-default-pairs",
        action="store_true",
        default=False,
        help="leave out the pairs file pitboss ships",
    ),
    name="lint",
)
def lint(args: argparse.Namespace) -> None:
    """Check texts: print one finding per line, exit 1 on any, 0 on none.

    Args:
        args: the parsed arguments.
    """
    KINDS[args.kind](args)
