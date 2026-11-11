"""The open PR of a worktree's branch, as ``hand-back-check`` reads it (pitboss#471)."""

import dataclasses
import json
import pathlib
from typing import Mapping, Sequence

from . import repositories, world
from .test_plan_check_step import check_comment

NUMBER = 7
BASE = "repos/owner/project"


def git(tree: pathlib.Path, *words: str) -> str:
    """Run git for real in a directory.

    Args:
        tree: the directory.
        *words: git's arguments.

    Returns:
        Its output, stripped.
    """
    return repositories.run_git(tree, *words).strip()


def _body(head: str) -> str:
    return (
        f"Fixes #7\n\n## Plan\nthe plan\n\n$ echo hi\n\n## Execution\nx\n\n"
        f"Head: {head}\n"
    )


def _check(body: str) -> Mapping[str, str]:
    comment = check_comment(body)
    return {**dataclasses.asdict(comment), "html_url": comment.url}


def _plant(
    here: world.World, tree: pathlib.Path, posted: Sequence[Mapping[str, str]]
) -> world.World:
    head, branch = git(tree, "rev-parse", "HEAD"), git(tree, "branch", "--show-current")
    pull = {
        "number": NUMBER,
        "title": "t",
        "created_at": "2026-11-11T00:00:00Z",
        "user": {"login": "x"},
        "body": _body(head),
        "head": {"sha": head, "ref": branch},
        "base": {"ref": "main"},
    }
    here.bodies[f"{BASE}/pulls?state=open&head=owner:{branch}"] = json.dumps([pull])
    here.bodies[f"{BASE}/pulls/{NUMBER}"] = json.dumps(pull)
    here.bodies[f"{BASE}/issues/{NUMBER}/comments?per_page=100&page=1"] = json.dumps(
        posted
    )
    return here


def ready(here: world.World, tree: pathlib.Path | None = None) -> world.World:
    """Plant the open PR of a worktree's branch with its clean Plan check posted.

    Args:
        here: the world.
        tree: the worktree (default: the main clone).

    Returns:
        The world.
    """
    top = tree or here.clone
    return _plant(here, top, [_check(_body(git(top, "rev-parse", "HEAD")))])


def unposted(here: world.World) -> world.World:
    """Plant the open PR of the main clone's branch with no Plan check posted.

    Args:
        here: the world.

    Returns:
        The world.
    """
    return _plant(here, here.clone, [])
