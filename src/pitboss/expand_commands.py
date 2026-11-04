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
        return evidencesplit.apply(store, text, args.limit)
    except evidencesplit.TooLong as error:
        raise _fail(f"{args.template}: {error}") from error


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

    Args:
        args: the parsed arguments (a template or directory it cannot use
            exits with status 2).
    """
    sys.stdout.write(_body(args))
