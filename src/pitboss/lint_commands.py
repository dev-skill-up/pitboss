"""The ``lint`` command: checks of the texts agents write."""

import argparse
import pathlib
import sys
from typing import Callable, Mapping

from gather.commands import add_argument

from . import ENTRY_DATA, phrases

USAGE_ERROR = 2


def _fail(message: str) -> SystemExit:
    print(message, file=sys.stderr)
    return SystemExit(USAGE_ERROR)


def _phrases(args: argparse.Namespace) -> list[phrases.Phrase]:
    found: list[phrases.Phrase] = []
    try:
        if not args.no_default_phrases:
            found.extend(phrases.parse(phrases.default_text(), "default phrases"))
        for path in args.phrases or ():
            found.extend(phrases.load(pathlib.Path(path)))
    except phrases.PhraseError as error:
        raise _fail(str(error)) from error
    return found


def _text(args: argparse.Namespace) -> None:
    banned = _phrases(args)
    refused: list[str] = []
    for name in args.files:
        try:
            text = phrases.read_text(pathlib.Path(name))
        except phrases.PhraseError as error:
            raise _fail(str(error)) from error
        refused.extend(phrases.findings(text, name, banned))
    for each in refused:
        print(each)
    if refused:
        raise SystemExit(1)
    print(f"ok: {len(banned)} phrases")


KINDS: Mapping[str, Callable[[argparse.Namespace], None]] = {"text": _text}


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
    name="lint",
)
def lint(args: argparse.Namespace) -> None:
    """Check texts: print one finding per line, exit 1 on any, 0 on none.

    Args:
        args: the parsed arguments.
    """
    KINDS[args.kind](args)
