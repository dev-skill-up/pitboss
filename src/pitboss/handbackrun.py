"""The worktree checks of ``hand-back-check`` (keyword: hand-back-done).

The worktree is ``--repo`` (default the current directory): its head, its git
directory and the processes under it are what is judged, wherever the command
runs. The PR is ``--pr`` or the open PR of the worktree's branch, and the check
of its head and of its posted Plan check is never skipped (pitboss#471).
"""

import argparse
import os
import pathlib
import re
import subprocess
from typing import Sequence

from . import config, ghapi, handbackcheck, handbackrecord


def git_out(args: argparse.Namespace, *words: str) -> str:
    """Run git in the worktree and answer its output.

    Args:
        args: the parsed arguments; ``repo`` is the worktree.
        *words: git's arguments.

    Returns:
        The output, stripped; empty when git failed.
    """
    try:
        done = args.safe_run(["git", "-C", str(args.repo), *words])
        return str(done.stdout).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _path(args: argparse.Namespace, kind: str) -> pathlib.Path:
    return pathlib.Path(git_out(args, "rev-parse", kind))


def _jobs_and_record(args: argparse.Namespace, head: str) -> Sequence[str]:
    root, proc = _path(args, "--show-toplevel"), pathlib.Path(args.processes)
    shown = [
        handbackcheck.jobs_line(handbackcheck.running_jobs(root, proc, os.getpid()))
    ]
    if handbackrecord.recorded(_path(args, "--absolute-git-dir"), head):
        shown.append(handbackcheck.second_line(head))
    return shown


ORIGIN = re.compile(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?/?$")


def _slug(args: argparse.Namespace, settings: config.Config) -> str:
    # case 31 (keyword: hand-back-origin): the repository is the worktree's origin
    found = ORIGIN.search(git_out(args, "remote", "get-url", "origin"))
    return found.group(1) if found else settings.project.repo.slug


def _pull_lines(
    args: argparse.Namespace, settings: config.Config, head: str
) -> Sequence[str]:
    github = ghapi.read_only(args.safe_run)
    slug = _slug(args, settings)
    number = args.pr
    if number is None:
        number = handbackcheck.branch_pull(
            github, slug, git_out(args, "rev-parse", "--abbrev-ref", "HEAD")
        )
    if isinstance(number, str):
        return [number]
    pushed = handbackcheck.Pushed(
        github=github,
        slug=slug,
        number=number,
        head=head,
        trusted=settings.review.trusted,
    )
    return handbackcheck.pull_lines(pushed)


def refusals(args: argparse.Namespace, settings: config.Config) -> Sequence[str]:
    """What stops a hand-back: a job still running, a second one, an unposted check.

    Args:
        args: the parsed arguments.
        settings: the configuration.

    Returns:
        The refusal lines; none when the worktree's head may be handed back.
    """
    head = git_out(args, "rev-parse", "HEAD")
    if not head:
        return [f"refused: {args.repo} is not a git worktree with a head"]
    return [
        each
        for each in (*_jobs_and_record(args, head), *_pull_lines(args, settings, head))
        if each
    ]


def accept(args: argparse.Namespace) -> None:
    """Record that a hand-back was accepted for the worktree's head.

    Args:
        args: the parsed arguments.
    """
    head = git_out(args, "rev-parse", "HEAD")
    handbackrecord.record(_path(args, "--absolute-git-dir"), head)
