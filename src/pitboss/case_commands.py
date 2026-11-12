"""The ``case`` command: edit a ticket's body, never its comments (pitboss#444)."""

import argparse
import json
import pathlib
import sys
from typing import Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, casepost, config, expand_commands, ghapi, ghstore

USAGE_ERROR = 2


def _pulls(text: str) -> Sequence[tuple[int, str]]:
    return [
        (int(each["number"]), str(each.get("body") or "")) for each in json.loads(text)
    ]


@ENTRY_DATA.register(
    add_argument("action", choices=("post",), help="post: the file into the body"),
    add_argument("ticket", help="OWNER/NAME#NUMBER: the ticket"),
    add_argument("file", help="the case, or with --done-when the new Done-when"),
    add_argument(
        "--done-when",
        action="store_true",
        default=False,
        help="replace the ticket's Done-when section with the file (default: add the"
        " file as a case at the end of the body)",
    ),
    name="case",
)
def case(args: argparse.Namespace) -> None:
    """Add a case to a ticket's body, or replace its Done-when; never a comment.

    The body is the only place a Done-when or a case is kept (A19, keyword:
    case-post); the command refuses, and changes nothing, once a PR says it
    fixes the ticket, since a worker started (A31: new findings go to an older
    open ticket). It prints the ticket's address; the exit status is 2 for a
    refusal or a file it cannot read.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 2, with the reason, for a refusal.
    """
    found = expand_commands.PULL.match(args.ticket)
    try:
        text = pathlib.Path(args.file).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise SystemExit(f"pitboss case post: {args.file}: {error}") from error
    if not found:
        print(
            f"pitboss case post: refused: {args.ticket}: not OWNER/NAME#NUMBER",
            file=sys.stderr,
        )
        raise SystemExit(USAGE_ERROR)
    slug, number = found.group(1), int(found.group(2))
    github = ghapi.GitHub(mutate=args.safe_run, run=args.safe_run)
    pulls = ghapi.pages(github, f"repos/{slug}/pulls?state=all", _pulls)
    repo = config.make_repo(*slug.split("/"))
    if why := casepost.refusal(
        args.ticket, casepost.started_by(args.ticket, pulls, repo)
    ):
        print(f"pitboss case post: refused: {why}", file=sys.stderr)
        raise SystemExit(USAGE_ERROR)
    path = f"repos/{slug}/issues/{number}"
    body = str(json.loads(ghapi.get(github, path)).get("body") or "")
    edit = casepost.with_done_when if args.done_when else casepost.with_case
    ghstore.send(github, "PATCH", path, edit(body, text))
    print(f"https://github.com/{slug}/issues/{number}")
