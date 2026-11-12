"""What ``pitboss push`` requires before it pushes anything (keyword: push).

Each check prints why and exits 1, so nothing is pushed: the declared pre-push
checks, a green ``pitboss nox`` on the tree, and a PR body that keeps its
Execution heading.
"""

import argparse
import pathlib
import subprocess
from typing import Sequence

from . import config, evidencepush, ghapi, noxcheck, noxgreen, prepush


def pre_push(
    args: argparse.Namespace,
    checks: Sequence[config.PrePush],
    directory: pathlib.Path,
) -> None:
    """Refuse a push unless each declared pre-push check says ok.

    The keyword is pre-push-check (bats#654): only an explicit ok counts.

    Args:
        args: the parsed arguments.
        checks: the declared checks.
        directory: where they run.

    Raises:
        SystemExit: 1 when a check is not ok; nothing is pushed.
    """
    lines = prepush.refusals(
        args.safe_run,
        checks,
        directory,
    )
    for each in lines:
        print(each)
    if lines:
        print("push refused: nothing was pushed; fix the check")
        raise SystemExit(1)


def green_nox(args: argparse.Namespace) -> None:
    """Refuse a push of a tree no green ``pitboss nox`` ran on.

    The keyword is nox-tree (pitboss#471): a repository with a noxfile.py pushes a
    tree that a green ``pitboss nox`` ran on, the tree hash and not the branch.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 when a session did not run green on the tree.
    """

    def out(*words: str) -> str:
        try:
            return str(args.safe_run(["git", *words]).stdout).strip()
        except (OSError, subprocess.CalledProcessError):  # pragma: no cover
            return ""

    root, tree = out("rev-parse", "--show-toplevel"), out("rev-parse", "HEAD^{tree}")
    directory = out("rev-parse", "--absolute-git-dir")
    if (
        not (root and tree and directory)
        or not (pathlib.Path(root) / "noxfile.py").exists()
    ):
        return
    ran = noxgreen.ran_green(pathlib.Path(directory), tree)
    absent = [each.value for each in noxcheck.WITHOUT_TESTS if each.value not in ran]
    if absent:
        print(noxgreen.missing_line(tree, absent))
        raise SystemExit(1)


def execution(
    args: argparse.Namespace,
    github: ghapi.GitHub,
    slug: str | None,
    wanted: Sequence[str],
) -> None:
    """Refuse a push whose PR body lost its Execution heading.

    Case 11 (keyword: execution-section): the body keeps its Execution heading.

    Args:
        args: the parsed arguments.
        github: the API.
        slug: the repository pushed to.
        wanted: the branches pushed.

    Raises:
        SystemExit: 1 when a body lost it; nothing is pushed.
    """
    for each in wanted:
        lost = evidencepush.missing_execution(args.safe_run, github, slug, each)
        for line in lost:
            print(line)
        if lost:
            print("push refused: nothing was pushed; edit the body of the PR")
            raise SystemExit(1)
