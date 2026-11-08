"""The ``plan-check`` command: a Plan's commands, run before it is approved.

This is the plan-check area (pitboss#192). Each row of the Plan but an Impact
command (``pitboss impact``, searched in a worktree of the PR's head, pitboss#320)
runs with ``sh -c`` in a scratch worktree of the PR's base (a row that runs nox
is not run but refused, pitboss#251), with the permissions of whoever
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
from typing import Iterator, Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, expansion, forms, impact, plancheck, plandigest

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
def scratch_worktree(args: argparse.Namespace, ref: str) -> Iterator[pathlib.Path]:
    """A detached worktree of a commit, removed when the block ends.

    Args:
        args: the parsed arguments (``repo``).
        ref: the commit: the base, or the head.

    Yields:
        The worktree's directory.
    """
    with tempfile.TemporaryDirectory(prefix="plan-check-") as scratch:
        tree = pathlib.Path(scratch) / "tree"
        _git(args, "worktree", "add", "--detach", str(tree), ref)
        try:
            yield tree
        finally:
            _git(args, "worktree", "remove", "--force", str(tree))


HEAD_OPTION = add_argument(
    "--head",
    default="",
    help="the PR's head, searched by an Impact command (default: the last"
    " `Head:` line of the body, else HEAD of the checkout)",
)


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
    HEAD_OPTION,
    add_argument(
        "--timeout",
        type=int,
        default=plancheck.TIMEOUT,
        help=f"the most seconds a command may run (default: {plancheck.TIMEOUT})",
    ),
    name="plan-check",
)
def plan_check(args: argparse.Namespace) -> None:
    """Run the commands of a Plan, and refuse it for a row that did not run.

    A nox row is refused unrun (pitboss#251). A row ``pitboss impact PHRASE...``
    is searched in a scratch worktree of the PR's head (``--head``, by default the
    last ``Head:`` line of the body, else HEAD of the checkout); the Plan is
    refused for a hit with no disposition line (``file:line: edited`` or ``not
    edited``) and for one citing a ``file:line`` that is no hit there (keyword:
    impact-list, pitboss#320).

    Prints a row for each command (its exit status and duration, or that it did
    not run), a line for each Impact finding, the Plan digest and the last
    line, ``Plan check: ok`` or ``Plan check: refused`` naming the rows that did
    not run and the number of Impact findings. The output is posted as a
    comment on the PR (keyword: plan-check, pitboss#192); ``pitboss next``
    offers a Plan review that has commands only after a comment that says
    ``Plan check: ok`` for this Plan.

    Args:
        args: the parsed arguments (a body it cannot read, without a ``## Plan``
            section or with a directive with no command exits with status 2).

    Raises:
        SystemExit: with status 1 when a row did not run or the Impact list has
            a finding.
    """
    output, failed = _read_and_checked(args)
    sys.stdout.write(output)
    if failed:
        raise SystemExit(REFUSED)


def _read_and_checked(args: argparse.Namespace) -> tuple[str, bool]:
    body = args.file.read()
    section = _plan_of(args.file.name, body)
    return _checked(args, section, _head_of(args, body))


def _head_of(args: argparse.Namespace, body: str) -> str:
    found = forms.HEAD_LINE.findall(body)
    return str(args.head or (found[-1] if found else "HEAD"))


def _checked(args: argparse.Namespace, section: str, ref: str) -> tuple[str, bool]:
    with (
        scratch_worktree(args, args.base) as tree,
        scratch_worktree(args, ref) as head,
    ):
        runner = functools.partial(run_in, args, tree, args.timeout)
        search = _searching(head)
        rows, refused = plancheck.report(section, runner, search)
        found = plancheck.impact_findings(section, search)
        return plancheck.text(section, rows, refused, found), bool(refused or found)


def _searching(tree: pathlib.Path) -> plancheck.Search:
    @functools.cache
    def once(phrases: tuple[str, ...]) -> Sequence[impact.Hit]:
        return impact.hits_in(tree, phrases)

    return lambda phrases: once(tuple(phrases))
