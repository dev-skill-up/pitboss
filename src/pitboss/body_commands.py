"""The ``body-digest`` command: the digest a review records for the PR body.

This is the body-digest area (pitboss#147), and the ``plan-digest`` command is
the plan-digest area (pitboss#172).
"""

import argparse
import pathlib
import re
import sys
from typing import Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, bodydigest, deviations, plandigest, workeractions

USAGE_ERROR = 2


def _fail(message: str) -> SystemExit:
    print(message, file=sys.stderr)
    return SystemExit(USAGE_ERROR)


def _read(name: str) -> str:
    try:
        return pathlib.Path(name).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise _fail(f"{name}: {error}") from error


BODY_FILE = add_argument("file", help="the PR body as `gh api` printed it, in a file")


def _plan_digest(name: str) -> str:
    found = bodydigest.of_section(plandigest.section(_read(name)))
    if not found:
        raise _fail(f"{name}: no `## Plan` section")
    return found


@ENTRY_DATA.register(BODY_FILE, name="body-digest")
def body_digest(args: argparse.Namespace) -> None:
    """Print the ``Body:`` line a review of the PR body in a file records.

    Args:
        args: the parsed arguments (a file it cannot read as UTF-8 exits with
            status 2).
    """
    print(f"{bodydigest.PREFIX}{bodydigest.digest(_read(args.file))}")


@ENTRY_DATA.register(
    add_argument("file", help="the worker's hand-back, in a file"),
    name="hand-back-check",
)
def hand_back_check(args: argparse.Namespace) -> None:
    """Print ``ok``, or the ``NOT STARTED`` text of a hand-back without the line.

    This is the deviations area (pitboss#257).

    Args:
        args: the parsed arguments (a file it cannot read as UTF-8 exits with
            status 2).

    Raises:
        SystemExit: 1 when the hand-back has no ``Deviations:`` line.
    """
    missing = deviations.not_started(_read(args.file))
    print(missing or "ok")
    if missing:
        raise SystemExit(1)


def _scan(entries: Sequence[str], patterns: Sequence[str]) -> Sequence[str]:
    try:
        return workeractions.scan(entries, patterns)
    except re.error as error:
        raise _fail(f"pattern: {error}") from error


@ENTRY_DATA.register(
    add_argument("output", help="a worker's whole output file (JSON lines)"),
    add_argument(
        "pattern",
        nargs="+",
        help="a regular expression, searched without regard to case",
    ),
    name="worker-actions",
)
def worker_actions(args: argparse.Namespace) -> None:
    """Print the tool calls and the final report of a worker's output that match.

    This is the worker-actions area (pitboss#352). A statement about what a
    worker did is made from this output. A line is the line number of the file,
    the tool and its input, or the line number and ``final report:`` with the
    report. With no match it prints ``no match in N calls and the final report``,
    which is reported with its count and never as "it did not".

    Args:
        args: the parsed arguments (a file it cannot read as UTF-8, or a
            pattern that is not a regular expression, exits with status 2).
    """
    for line in _scan(_read(args.output).splitlines(), args.pattern):
        print(line)


@ENTRY_DATA.register(BODY_FILE, name="plan-digest")
def plan_digest(args: argparse.Namespace) -> None:
    """Print the ``Plan digest:`` line a review of the Plan in a file records.

    Args:
        args: the parsed arguments (a file it cannot read as UTF-8, or whose
            body has no ``## Plan`` section, exits with status 2).
    """
    print(f"{bodydigest.PLAN_PREFIX}{_plan_digest(args.file)}")
