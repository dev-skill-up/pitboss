"""The ``plan-check`` command: a Plan's commands, run before it is approved.

This is the plan-check area (pitboss#192). Each command of the Plan runs with
``sh -c`` in a scratch worktree of the PR's base, with the permissions of whoever
runs ``pitboss plan-check``, so the body is the worker's own and is never read
from somewhere else (it is the file the caller saved, as ``expand`` reads its
template).
"""

import argparse
import contextlib
import functools
import pathlib
import subprocess
import sys
import tempfile
import time
from typing import Iterator

from gather.commands import add_argument

from . import ENTRY_DATA, expansion, plancheck, plandigest

USAGE_ERROR = 2
REFUSED = 1
QUIET = {
    "check": False,
    "capture_output": False,
    "stdin": subprocess.DEVNULL,
    "stdout": subprocess.DEVNULL,
    "stderr": subprocess.DEVNULL,
}


def _fail(message: str) -> SystemExit:
    print(message, file=sys.stderr)
    return SystemExit(USAGE_ERROR)


def status_in(
    args: argparse.Namespace, directory: pathlib.Path, timeout: int, command: str
) -> int | str:
    """Run one command line in a directory, with a time limit.

    The output is discarded (a pipe a stray child holds open would outlast the
    limit), and nothing is read from the terminal.

    Args:
        args: the parsed arguments.
        directory: the working directory.
        timeout: the most seconds the command may run.
        command: the command line, for ``sh -c``.

    Returns:
        Its exit status, or the text that says why it did not finish.
    """
    try:
        done = args.safe_run(
            ["sh", "-c", command], cwd=directory, timeout=timeout, **QUIET
        )
    except subprocess.TimeoutExpired:
        return f"timed out after {timeout}s"
    except OSError as error:
        return f"cannot start ({error})"
    return int(done.returncode)


def run_in(
    args: argparse.Namespace, directory: pathlib.Path, timeout: int, command: str
) -> plancheck.Run:
    """Run one command line in a directory, and time it.

    Args:
        args: the parsed arguments.
        directory: the working directory.
        timeout: the most seconds the command may run.
        command: the command line, for ``sh -c``.

    Returns:
        What it did.
    """
    started = time.monotonic()
    outcome = status_in(args, directory, timeout, command)
    seconds = time.monotonic() - started
    if isinstance(outcome, str):
        return plancheck.cut_off(outcome, seconds)
    return plancheck.finished(outcome, seconds)


def _git(args: argparse.Namespace, *words: str) -> None:
    try:
        args.safe_run(["git", "-C", args.repo, *words], check=True, capture_output=True)
    except (subprocess.CalledProcessError, OSError) as error:
        raise _fail(f"git {' '.join(words)}: {error}") from error


@contextlib.contextmanager
def scratch_worktree(args: argparse.Namespace) -> Iterator[pathlib.Path]:
    """A detached worktree of the base, removed when the block ends.

    Args:
        args: the parsed arguments (``repo`` and ``base``).

    Yields:
        The worktree's directory.
    """
    with tempfile.TemporaryDirectory(prefix="plan-check-") as scratch:
        tree = pathlib.Path(scratch) / "tree"
        _git(args, "worktree", "add", "--detach", str(tree), args.base)
        try:
            yield tree
        finally:
            _git(args, "worktree", "remove", "--force", str(tree))


def _plan_of(name: str, body: str) -> str:
    section = plandigest.section(body)
    if not section:
        raise _fail(f"{name}: no `## Plan` section")
    try:
        expansion.commands(section)
    except expansion.TemplateError as error:
        raise _fail(f"{name}: {error}") from error
    return section


@ENTRY_DATA.register(
    add_argument(
        "file",
        type=argparse.FileType("r", encoding="utf-8"),
        help="the PR body as `gh api` printed it, in a file",
    ),
    add_argument(
        "--repo",
        default=".",
        help="a checkout of the PR's repository (default: the current directory)",
    ),
    add_argument(
        "--base",
        default="origin/main",
        help="the PR's base, which the scratch worktree is made of (default:"
        " origin/main)",
    ),
    add_argument(
        "--timeout",
        type=int,
        default=plancheck.TIMEOUT,
        help=f"the most seconds a command may run (default: {plancheck.TIMEOUT})",
    ),
    name="plan-check",
)
def plan_check(args: argparse.Namespace) -> None:
    """Run each command of a Plan, and refuse the Plan if one does not run.

    Prints a row for each command (its exit status and duration, or that it did
    not run: it could not start or it timed out), the Plan digest and the last
    line, ``Plan check: ok`` or ``Plan check: refused`` naming each row that did
    not run. The output is posted as a comment on the PR (keyword: plan-check,
    pitboss#192); ``pitboss next`` offers a Plan review that has commands only
    after a comment that says ``Plan check: ok`` for this Plan.

    Args:
        args: the parsed arguments (a body it cannot read, without a ``## Plan``
            section or with a directive with no command exits with status 2).

    Raises:
        SystemExit: with status 1 when a row did not run.
    """
    section = _plan_of(args.file.name, args.file.read())
    with scratch_worktree(args) as tree:
        runner = functools.partial(run_in, args, tree, args.timeout)
        rows, refused = plancheck.report(section, runner)
    sys.stdout.write(plancheck.text(section, rows, refused))
    if refused:
        raise SystemExit(REFUSED)
