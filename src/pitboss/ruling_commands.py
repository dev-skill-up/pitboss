"""The ``ruling`` command: post an Opus ruling file as a PR comment (pitboss#466)."""

import argparse
import pathlib
import sys

from gather.commands import add_argument

from . import ENTRY_DATA, expand_commands, ghapi, ghstore, rulingform

USAGE_ERROR = 2


@ENTRY_DATA.register(
    add_argument("action", choices=("post",), help="post: the file as a comment"),
    add_argument("pull", help="OWNER/NAME#NUMBER: the pull request"),
    add_argument("file", help="the ruling, in a file"),
    name="ruling",
)
def ruling(args: argparse.Namespace) -> None:
    """Post an Opus ruling file as a comment on a PR and print the comment's URL.

    This is the ruling-post area (pitboss#466): ``gh api -F body=@file`` was
    denied by the permission classifier four times. The file is refused, and
    nothing is posted, unless its first line is exactly ``Opus ruling``, its
    second line is ``Ruling: <word>`` with a word of the ruling words, and it
    has a ``How we got here`` section with the analysis in it. It posts as it
    is run, with no flag; the exit status is 2 for a refusal or a file it
    cannot read.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 2, with the reason, for a refusal.
    """
    found = expand_commands.PULL.match(args.pull)
    try:
        text = pathlib.Path(args.file).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise SystemExit(f"pitboss ruling post: {args.file}: {error}") from error
    why = rulingform.refusal(text) if found else f"{args.pull}: not OWNER/NAME#NUMBER"
    if why or not found:
        print(f"pitboss ruling post: refused: {why}", file=sys.stderr)
        raise SystemExit(USAGE_ERROR)
    github = ghapi.GitHub(mutate=args.safe_run, run=args.safe_run)
    path = f"repos/{found.group(1)}/issues/{int(found.group(2))}/comments"
    print(ghstore.post(github, path, text).url)
