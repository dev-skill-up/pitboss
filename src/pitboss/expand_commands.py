"""The ``expand`` command: a template of shell commands becomes a body.

This is the expand area (pitboss#117). Each directive runs with ``sh -c`` in the
given checkout, with the permissions of whoever runs ``pitboss expand``, so the
template is the worker's own and is never read from somewhere else (a pull
request's text, another person's branch).
"""

import argparse
import functools
import pathlib
import re
import subprocess
import sys

from gather.commands import add_argument

from . import ENTRY_DATA, evidencesplit, expansion, ghstore

USAGE_ERROR = 2
PULL = re.compile(r"^([\w.-]+/[\w.-]+)#(\d+)$")


def _fail(message: str) -> SystemExit:
    print(message, file=sys.stderr)
    return SystemExit(USAGE_ERROR)


def run_in(
    args: argparse.Namespace, directory: pathlib.Path, command: str
) -> expansion.Outcome:
    """Run one command line in a directory.

    Standard error is joined to standard output, as a terminal shows them, and
    the bytes are decoded without losing any (an invalid byte is shown as a
    backslash escape).

    Args:
        args: the parsed arguments.
        directory: the working directory.
        command: the command line, for ``sh -c``.

    Returns:
        The exit status and the output.
    """
    done = args.safe_run(
        ["sh", "-c", command],
        cwd=directory,
        check=False,
        capture_output=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=False,
    )
    return expansion.Outcome(
        status=done.returncode,
        output=done.stdout.decode("utf-8", errors="backslashreplace"),
    )


def _expanded(args: argparse.Namespace) -> str:
    directory = pathlib.Path(args.cwd)
    if not directory.is_dir():
        raise _fail(f"{args.cwd}: not a directory")
    try:
        template = pathlib.Path(args.template).read_text(encoding="utf-8")
        return expansion.expand(template, functools.partial(run_in, args, directory))
    except (OSError, UnicodeError, expansion.TemplateError) as error:
        raise _fail(f"{args.template}: {error}") from error


MERGE_NOTICE = (
    "HEAD {head} is a merge: if you merged main to resolve a conflict, the Plan"
    " section is unchanged but its hits moved; run `pitboss plan-check` against"
    " the merge head (`--head {head}`), which refuses a disposition line whose"
    " file:line is not a hit of its row at that head (keyword: merge-head,"
    " pitboss#317)\n"
)


def _merge_notice(args: argparse.Namespace) -> str:
    # a merge commit at the head: the hits of the Plan's Impact rows may have moved
    try:
        done = args.safe_run(
            ["git", "-C", args.cwd, "rev-list", "--parents", "-n", "1", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return ""
    head, *parents = str(done.stdout).split()
    return MERGE_NOTICE.format(head=head) if len(parents) > 1 else ""


def _body(args: argparse.Namespace) -> str:
    text = _expanded(args)
    if not args.pr:
        return text
    found = PULL.match(args.pr)
    if not found:
        raise _fail(f"{args.pr}: not OWNER/NAME#NUMBER")
    runners = (args.safe_run, args.run)
    store = ghstore.store_of(runners, found.group(1), int(found.group(2)))
    try:
        done = evidencesplit.place(store, text, args.limit)
    except evidencesplit.TooLong as error:
        raise _fail(f"{args.template}: {error}") from error
    sys.stderr.write(done.notice + _merge_notice(args))
    return done.body


@ENTRY_DATA.register(
    add_argument("template", help="the template file: text with `$ command` lines"),
    add_argument(
        "--cwd",
        default=".",
        help="the checkout the commands run in (default: the current directory)",
    ),
    add_argument(
        "--pr",
        default="",
        help="OWNER/NAME#NUMBER: set the pull request's description to the "
        "body, the parts past --limit in comments (a dry run unless "
        "--no-dry-run); a rerun rewrites its own comments",
    ),
    add_argument("--no-dry-run", action="store_true", default=False),
    add_argument(
        "--limit",
        type=int,
        default=evidencesplit.LIMIT,
        help="the most characters of a description or a comment (default: "
        f"{evidencesplit.LIMIT})",
    ),
    name="expand",
)
def expand(args: argparse.Namespace) -> None:
    """Print a template with each ``$ command`` line run and its output shown.

    Each command is printed as written and followed by its raw output, in a
    fenced block marked as produced by expand; the exit status follows when it
    is not zero. Nothing is trimmed or filtered, and nothing but a command
    supplies a fact. With ``--pr`` the body is also set as the pull request's
    description, and a body over ``--limit`` is cut on paragraph markers: the
    later parts become comments, cited by URL in the description (keyword:
    expand-split, pitboss#177).
    Standard error then says that the overflow is the standing decision, with
    each comment's URL, and the description's section starts with the same
    sentence (keyword: expand-split, pitboss#317). When the
    checkout's HEAD is a merge commit, standard error says to run ``plan-check``
    again against it (keyword: merge-head, pitboss#317).

    Args:
        args: the parsed arguments (a template or directory it cannot use
            exits with status 2).
    """
    sys.stdout.write(_body(args))
