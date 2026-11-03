"""The ``body-digest`` command: the digest a review records for the PR body.

This is the body-digest area (pitboss#147).
"""

import argparse
import pathlib
import sys

from gather.commands import add_argument

from . import ENTRY_DATA, bodydigest

USAGE_ERROR = 2


def _fail(message: str) -> SystemExit:
    print(message, file=sys.stderr)
    return SystemExit(USAGE_ERROR)


def _read(name: str) -> str:
    try:
        return pathlib.Path(name).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise _fail(f"{name}: {error}") from error


@ENTRY_DATA.register(
    add_argument("file", help="the PR body as `gh api` printed it, in a file"),
    name="body-digest",
)
def body_digest(args: argparse.Namespace) -> None:
    """Print the ``Body:`` line a review of the PR body in a file records.

    Args:
        args: the parsed arguments (a file it cannot read as UTF-8 exits with
            status 2).
    """
    print(f"{bodydigest.PREFIX}{bodydigest.digest(_read(args.file))}")
