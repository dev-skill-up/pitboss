"""The ``owner-pause`` command: label a PR ``paused-owner`` and post the question."""

import argparse
import pathlib
import sys

from gather.commands import add_argument

from . import ENTRY_DATA, expand_commands, ghapi, ghstore, ownerpause, steps

USAGE_ERROR = 2


@ENTRY_DATA.register(
    add_argument("pull", help="OWNER/NAME#NUMBER: the pull request"),
    add_argument("file", help="the question for the owner, in a file"),
    name="owner-pause",
)
def owner_pause(args: argparse.Namespace) -> None:
    """Pause a PR for the owner: put the ``paused-owner`` label, post the question.

    The question is refused, and nothing is changed, unless it names the options
    (a line that starts with ``Options``) and has a ``How we got here`` section.
    The label goes on first and the question is posted as a comment; the
    comment's URL is printed (A5, keyword: owner-pause). The exit status is 2
    for a refusal or a file it cannot read.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 2, with the reason, for a refusal.
    """
    found = expand_commands.PULL.match(args.pull)
    try:
        text = pathlib.Path(args.file).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise SystemExit(f"pitboss owner-pause: {args.file}: {error}") from error
    why = ownerpause.refusal(text) if found else f"{args.pull}: not OWNER/NAME#NUMBER"
    if why or not found:
        print(f"pitboss owner-pause: refused: {why}", file=sys.stderr)
        raise SystemExit(USAGE_ERROR)
    slug, number = found.group(1), int(found.group(2))
    github = ghapi.GitHub(mutate=args.safe_run, run=args.safe_run)
    path = ownerpause.label_path(slug, number)
    github.mutate(
        ["gh", "api", "-X", "POST", "-f", f"labels[]={steps.PAUSED_LABEL}", path]
    )
    print(ghstore.post(github, f"repos/{slug}/issues/{number}/comments", text).url)
