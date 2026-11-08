"""The ``impact`` command: the hits that make a Plan's Impact list.

This is the impact-list area (pitboss#320); the search is ``impact``.
"""

import argparse
import pathlib
import sys

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

    The search is of the whole directory at its head, not of the index, without
    regard to case, with any whitespace (a line break and the marks that
    continue a wrapped sentence included) between the words of a phrase, and
    leaves out only ``.git``, ``build``, ``skill-zips`` and the caches. A Plan
    cites this command, so its Evidence block is the Impact list, and ``pitboss
    plan-check`` holds the Plan to it (keyword: impact-list, pitboss#320).

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
