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

from . import (
    ENTRY_DATA,
    bodydigest,
    bodyhead,
    cloneguard,
    configfile,
    configsettle,
    deviations,
    expand_commands,
    expansion,
    plandigest,
    workeractions,
)

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
    found = expansion.section_digest(plandigest.section(_read(name)))
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
    add_argument(
        "--config",
        default=None,
        help="the project's configuration (a path, or a name in"
        " .claude/pitboss/<name>.toml; default: the search, else the fetch). Every"
        " clone it names (main_clone, and the library clones under the workspace)"
        " must be on its default branch with no uncommitted change to a tracked"
        " file, else a `refused` line names the clone and its branch",
    ),
    name="hand-back-check",
)
def hand_back_check(args: argparse.Namespace) -> None:
    """Print ``ok``, or why the hand-back is refused.

    This is the deviations area (pitboss#257) and the clone-guard area
    (pitboss#297): a hand-back without the line is ``NOT STARTED``, and a clone
    of the configuration off its default branch or with an uncommitted change
    is a ``refused`` line naming it and its branch.

    Args:
        args: the parsed arguments (a file it cannot read as UTF-8 exits with
            status 2).

    Raises:
        SystemExit: 1 when the hand-back has no ``Deviations:`` line or a clone
            is not on its default branch with a clean tree.
    """
    missing = deviations.not_started(_read(args.file))
    configsettle.find_or_say(args)
    refused = cloneguard.refusals(args, configfile.working_directory(args))
    for each in (missing, *refused):
        if each:
            print(each)
    if not (missing or refused):
        print("ok")
    else:
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

    The digest takes each block ``pitboss expand`` produced as its command line
    (keyword: plan-digest-collapse, pitboss#358).

    Args:
        args: the parsed arguments (a file it cannot read as UTF-8, or whose
            body has no ``## Plan`` section, exits with status 2).
    """
    print(f"{bodydigest.PLAN_PREFIX}{_plan_digest(args.file)}")


PULL_ARGUMENT = add_argument("pull", help="OWNER/NAME#NUMBER: a pull request")


def _pull(text: str) -> tuple[str, int]:
    found = expand_commands.PULL.match(text)
    if found is None:
        raise _fail(f"{text}: not OWNER/NAME#NUMBER")
    return found.group(1), int(found.group(2))


@ENTRY_DATA.register(PULL_ARGUMENT, name="body-head")
def body_head(args: argparse.Namespace) -> None:
    """Add the ``Head:`` line of the PR's head to its body, after a merge of main.

    This is the body-head area (pitboss#369). The one change to the body that a
    merge of the base requires: a line ``Head: <the head now>`` after the last
    ``Head:`` line, nothing else changed (``text-lint`` reads the last one). It
    prints the new body's ``Body:`` digest line and the input of ``bats
    merge-proof`` (the head the body named, then the head now). It changes the
    body as it is run, with no flag; a body whose last ``Head:`` line is the
    head is not changed.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 2 for a body with no ``Head: <40 hex>`` line.
    """
    slug, number = _pull(args.pull)
    path = f"repos/{slug}/pulls/{number}"
    done = bodyhead.move(args.safe_run, args.safe_run, path)
    if done is None:
        print(f"{args.pull}: the body has no line `Head: <40 hex>`", file=sys.stderr)
        raise SystemExit(USAGE_ERROR)
    print(f"{bodydigest.PREFIX}{done.digest}")
    print(f"bats merge-proof {done.old} {done.new}")
