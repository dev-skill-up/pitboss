"""The ``impact`` command: the hits that make a Plan's Impact list.

This is the impact-list area (pitboss#320); the search is ``impact``.
"""

import argparse
import pathlib
import sys
from typing import Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, impact

USAGE_ERROR = 2


@ENTRY_DATA.register(
    add_argument("phrases", nargs="+", help="a phrase: words, any case, any spacing"),
    add_argument(
        "--root",
        default=".",
        help="the checkout to search (default: the current directory)",
    ),
    name="impact",
)
def impact_command(args: argparse.Namespace) -> None:
    """Print every line of the tree where a phrase starts, as ``file:line:text``.

    The search is of the whole directory at its head, not of the index, in any
    case, with any whitespace (a line break and the marks that continue a
    wrapped sentence included) between a phrase's words. It leaves out ``.git``,
    the root ``build`` and ``skill-zips``, caches, links and NUL-byte files. A Plan
    cites this command, so its Evidence block is the Impact list, and ``pitboss
    plan-check`` holds the Plan to it (keyword: impact-list, pitboss#320). On
    standard error it prints the phrases it searched, and a hint for a phrase of
    several words when the tree has the same words joined by underscores
    (``come first`` and ``come_first``), which the phrase does not match
    (keyword: impact-phrase, pitboss#317).

    Args:
        args: the parsed arguments (a root that is not a directory, or a phrase
            with no word, exits with status 2).

    Raises:
        SystemExit: with status 2 for a usage error.
    """
    root = pathlib.Path(args.root)
    if not root.is_dir():
        print(f"{args.root}: not a directory", file=sys.stderr)
        raise SystemExit(USAGE_ERROR)
    try:
        found = impact.hits_in(root, args.phrases)
    except impact.PhraseError as error:
        print(f"{error}", file=sys.stderr)
        raise SystemExit(USAGE_ERROR) from error
    sys.stdout.write("".join(f"{impact.shown(each)}\n" for each in found))
    _say_searched(root, args.phrases)


def _say_searched(root: pathlib.Path, phrases: Sequence[str]) -> None:
    # standard error, so the Evidence's list on standard output is only the hits
    print(
        "searched: " + "; ".join(f"`{each}`" for each in phrases),
        file=sys.stderr,
    )
    for form in impact.underscore_forms(root, phrases):
        print(
            f"hint: a phrase of several words matches words apart, and the tree"
            f" has `{form}`: search `{form}` too",
            file=sys.stderr,
        )
