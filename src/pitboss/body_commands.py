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
    commands,
    cloneguard,
    configfile,
    configsettle,
    deviations,
    expand_commands,
    handbackrun,
    expansion,
    partial,
    envrules,
    repositoryrule,
    plandigest,
    workeractions,
    workeredits,
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
        help=(
            "the project's configuration (a path, or a name in"
            " .claude/pitboss/<name>.toml; default: the search, else the fetch). Every"
            " clone it names (main_clone, and the library clones under the workspace)"
            " must be on its default branch with no uncommitted change to a tracked"
            " file, else a `refused` line names the clone and its branch"
        ),
    ),
    add_argument(
        "--pr",
        type=int,
        default=None,
        help=(
            "the PR number in the configuration's repository (default: the open PR"
            " of the worktree's branch, none is a refusal): the hand-back is refused"
            " unless the PR holds the worktree's head, its body ends with a `Head:`"
            " line naming it and a clean Plan check is posted"
        ),
    ),
    add_argument(
        "--repo",
        default=".",
        help=(
            "the worker's worktree (default: the current directory): its head, its"
            " git directory and the processes under it are judged"
        ),
    ),
    add_argument(
        "--output",
        default=None,
        help=(
            "the worker's whole output file (JSON lines): its file edit tools are"
            " listed, and an edit of a file outside the worktree or a shell command"
            " that edits files is refused (B16, keyword: worker-edits)"
        ),
    ),
    add_argument(
        "--processes",
        default="/proc",
        help=(
            "the directory of process entries (default: /proc): a process"
            " running in the worktree that is not this command is a job you started"
        ),
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
    text = _read(args.file)
    missing = deviations.not_started(text)
    configsettle.find_or_say(args)
    lines = [each for each in (missing, *_refusals(args, text)) if each]
    for each in lines:
        print(each)
    if lines:
        raise SystemExit(1)
    handbackrun.accept(args)  # recorded only when nothing at all refused
    print("ok")


def _refusals(args: argparse.Namespace, text: str) -> Sequence[str]:
    # the clone's, the jobs', the partial hand-back's (B17, keyword: partial-hand-back)
    # and the edits' (B16, keyword: worker-edits); the EDIT TOOLS line only informs
    found = [
        *cloneguard.refusals(args, configfile.working_directory(args)),
        *handbackrun.refusals(args, commands.load_settings(args)),
        partial.refusal(text),
        repositoryrule.refusal(text),
        envrules.give_up_refusal(text),  # keyword: env-check (quire#1065)
    ]
    edits = _edits(args)
    for each in edits[:1]:
        print(each)
    return [*found, *edits[1:]]


def _edits(args: argparse.Namespace) -> Sequence[str]:
    if args.output is None:
        return []
    root = pathlib.Path(handbackrun.git_out(args, "rev-parse", "--show-toplevel"))
    return workeredits.lines(_read(args.output).splitlines(), root)


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
    merge-proof`` (the head the newest approving review names, then the head now).
    It changes the body as it is run, with no flag; a body whose last ``Head:``
    line is the head is not changed.

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
    print(_proof(done.reviewed, done.new))


def _proof(reviewed: str, new: str) -> str:
    # keyword: merge-proof (pitboss#394): the reviewed SHA, then the head now
    if reviewed:
        return f"bats merge-proof {reviewed} {new}"
    return (
        "no approving review names a head: `bats merge-proof` needs the SHA"
        " of a review that approved, so get an adversarial review first"
    )
