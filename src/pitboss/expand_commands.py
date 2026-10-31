"""The ``expand`` command: a template of shell commands becomes a body.

keyword: expand (pitboss#117). Trust boundary: each directive runs with
``sh -c`` in the given checkout, with the permissions of whoever runs
``pitboss expand``, so the template is the worker's own and is never read from
somewhere else (a pull request's text, another person's branch).
"""

import argparse
import functools
import pathlib
import sys

from gather.commands import add_argument

from . import ENTRY_DATA, expansion

USAGE_ERROR = 2


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
        stdout=-1,
        stderr=-2,
        text=False,
    )
    return expansion.Outcome(
        status=done.returncode,
        output=done.stdout.decode("utf-8", errors="backslashreplace"),
    )


@ENTRY_DATA.register(
    add_argument("template", help="the template file: text with `$ command` lines"),
    add_argument(
        "--cwd",
        default=".",
        help="the checkout the commands run in (default: the current directory)",
    ),
    name="expand",
)
def expand(args: argparse.Namespace) -> None:
    """Print a template with each ``$ command`` line run and its output shown.

    Each command is printed as written and followed by its raw output, in a
    fenced block marked as produced by expand; the exit status follows when it
    is not zero. Nothing is trimmed or filtered, and nothing but a command
    supplies a fact.

    Args:
        args: the parsed arguments.
    """
    try:
        template = pathlib.Path(args.template).read_text(encoding="utf-8")
        directory = pathlib.Path(args.cwd)
        if not directory.is_dir():
            raise NotADirectoryError(f"{args.cwd}: not a directory")
        shell = functools.partial(run_in, args, directory)
        body = expansion.expand(template, shell)
    except (OSError, UnicodeError, expansion.TemplateError) as error:
        print(f"{args.template}: {error}", file=sys.stderr)
        raise SystemExit(USAGE_ERROR) from error
    sys.stdout.write(body)
