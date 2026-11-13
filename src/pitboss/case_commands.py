"""The ``case`` command: edit a ticket's body, never its comments (pitboss#444)."""

import argparse

from gather.commands import add_argument

from . import ENTRY_DATA, casepost, config, ghstore, pullfile


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

    """
    slug, number, text = pullfile.read("case post", args.ticket, args.file)
    github = pullfile.github_of(args)
    pulls = ghstore.pull_bodies(github, slug)
    repo = config.make_repo(*slug.split("/"))
    started = casepost.started_by(args.ticket, pulls, repo)
    if why := casepost.refusal(args.ticket, started):
        pullfile.refuse("case post", why)
    path = f"repos/{slug}/issues/{number}"
    body = ghstore.body(github, path)
    edit = casepost.with_done_when if args.done_when else casepost.with_case
    ghstore.send(github, "PATCH", path, edit(body, text))
    print(f"https://github.com/{slug}/issues/{number}")
