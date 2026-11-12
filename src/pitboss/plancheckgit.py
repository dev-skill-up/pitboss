"""The git of ``plan-check``: scratch worktrees of the base and the head, and diffs.

This is the plan-check area (pitboss#192).
"""

import argparse
import contextlib
import pathlib
import subprocess
import sys
import tempfile
from typing import Iterator, Sequence

from . import cipointercheck, devpath

USAGE_ERROR = 2


def usage_error(message: str) -> SystemExit:
    """Say a usage error.

    Args:
        message: what is wrong.

    Returns:
        The exit to raise (status 2).
    """
    print(message, file=sys.stderr)
    return SystemExit(USAGE_ERROR)


def git(args: argparse.Namespace, *words: str) -> str:
    """Run git in the checkout.

    Args:
        args: the parsed arguments (``repo``, ``safe_run``).
        *words: git's words.

    Returns:
        What it printed.

    Raises:
        usage_error: when git fails.
    """
    try:
        done = args.safe_run(
            ["git", "-C", args.repo, *words],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError) as error:
        raise usage_error(f"git {' '.join(words)}: {error}") from error
    return str(done.stdout)


@contextlib.contextmanager
def scratch_worktree(args: argparse.Namespace, ref: str) -> Iterator[pathlib.Path]:
    """A detached worktree of a commit, removed when the block ends.

    Args:
        args: the parsed arguments (``repo``).
        ref: the commit: the base, or the head.

    Yields:
        The worktree's directory.

    Raises:
        usage_error: when the temporary directory is under ``/dev``, where nothing is
            removed (#424).
    """
    refused = devpath.temporary_under_dev()
    if refused:
        raise usage_error(f"plan-check: no scratch worktree, {refused}")
    with tempfile.TemporaryDirectory(prefix="plan-check-") as scratch:
        tree = pathlib.Path(scratch) / "tree"
        git(args, "worktree", "add", "--detach", str(tree), ref)
        try:
            yield tree
        finally:
            git(args, "worktree", "remove", "--force", str(tree))


def added(args: argparse.Namespace, ref: str) -> Sequence[str]:
    """The paths the PR adds: the head against its merge base with the base.

    Args:
        args: the parsed arguments (``base``).
        ref: the head.

    Returns:
        The paths.
    """
    return names(args, ref, "--diff-filter=A")


def names(args: argparse.Namespace, ref: str, *flags: str) -> Sequence[str]:
    """The paths of the head against its merge base with the base.

    Args:
        args: the parsed arguments (``base``).
        ref: the head.
        *flags: more flags of ``git diff``.

    Returns:
        The paths.
    """
    words = ["diff", "--name-only", "-z", *flags, f"{args.base}...{ref}"]
    return [each for each in git(args, *words).split("\0") if each]


def diff(args: argparse.Namespace, ref: str, *flags: str) -> str:
    """The diff of the head against its merge base with the base.

    Args:
        args: the parsed arguments (``base``).
        ref: the head.
        *flags: the flags of ``git diff``.

    Returns:
        The diff.
    """
    # keyword: markup-lines (pitboss#343, #373): the lines the PR adds to each
    # file (--numstat -z) and its hunks, to tell a cut span from a new line (-U0)
    return git(args, "diff", *flags, "--no-renames", f"{args.base}...{ref}")


def reading(tree: pathlib.Path) -> cipointercheck.Read:
    """What reads a file of a tree.

    Args:
        tree: the tree.

    Returns:
        The reader: a file's text, None for no file.
    """

    def read(path: str) -> str | None:
        found = tree / path
        if not found.is_file():
            return None
        return found.read_text(encoding="utf-8", errors="replace")

    return read


def sha(args: argparse.Namespace, ref: str) -> str:
    """The commit a ref names.

    Args:
        args: the parsed arguments.
        ref: the ref.

    Returns:
        Its SHA.
    """
    return git(args, "rev-parse", ref).strip()
