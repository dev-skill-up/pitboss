"""The arguments of a command that posts a file to a PR or ticket (keyword: pull-file).

``ruling post``, ``owner-pause`` and ``case post`` take ``OWNER/NAME#NUMBER`` and a
file, refuse with status 2 and say why, and change nothing when they refuse. The
module reads the file it is given.
"""

import argparse
import pathlib
import re
import sys
from typing import Callable, NoReturn

from . import ghapi, ghstore

USAGE_ERROR = 2
PULL = re.compile(r"^([\w.-]+/[\w.-]+)#(\d+)$")


def refuse(command: str, why: str) -> NoReturn:
    """Say why a command refuses; it never returns, it ends the command.

    Args:
        command: the command as the user types it.
        why: the reason.

    Raises:
        SystemExit: always, with status 2.
    """
    print(f"pitboss {command}: refused: {why}", file=sys.stderr)
    raise SystemExit(USAGE_ERROR)


def read(command: str, pull: str, name: str) -> tuple[str, int, str]:
    """Read the file and the reference a command was given.

    Args:
        command: the command as the user types it.
        pull: ``OWNER/NAME#NUMBER``.
        name: the file's path.

    Returns:
        The repository's ``owner/name``, the number and the file's text.

    Raises:
        SystemExit: when the file cannot be read, or the reference is none (a
            refusal, status 2).
    """
    try:
        text = pathlib.Path(name).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise SystemExit(f"pitboss {command}: {name}: {error}") from error
    found = PULL.match(pull)
    if not found:
        refuse(command, f"{pull}: not OWNER/NAME#NUMBER")
    return found.group(1), int(found.group(2)), text


def github_of(args: argparse.Namespace) -> ghapi.GitHub:
    """The API of a command that changes GitHub as it is run.

    Args:
        args: the parsed arguments.

    Returns:
        The API, whose reads and changes both go through the safe runner.
    """
    return ghapi.GitHub(mutate=args.safe_run, run=args.safe_run)


def comment(github: ghapi.GitHub, slug: str, number: int, text: str) -> str:
    """Post a comment on a PR or ticket.

    Args:
        github: the API.
        slug: the repository's ``owner/name``.
        number: the PR's or ticket's number.
        text: the comment.

    Returns:
        The comment's address.
    """
    return ghstore.post(github, f"repos/{slug}/issues/{number}/comments", text).url


def post_comment(
    args: argparse.Namespace,
    command: str,
    check: Callable[[ghapi.GitHub, str, int, str], str],
    before: Callable[[ghapi.GitHub, str, int], object] | None = None,
) -> None:
    """Post the file as a comment on the PR, unless the check refuses it.

    Args:
        args: the parsed arguments, with a ``pull`` and a ``file``.
        command: the command as the user types it.
        check: says why the text may not be posted; empty when it may.
        before: changes something first (a label), once the check passed.
    """
    slug, number, text = read(command, args.pull, args.file)
    github = github_of(args)
    if why := check(github, slug, number, text):
        refuse(command, why)
    if before:
        before(github, slug, number)
    print(comment(github, slug, number, text))
