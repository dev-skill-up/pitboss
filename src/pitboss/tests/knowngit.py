"""The git checkouts the act cases push from.

An origin and a worktree with one commit of work, and the ticket of a checkout.
"""

import pathlib

from .. import rulefiles
from . import captured, scratch


def git(directory: pathlib.Path, *words: str) -> str:
    """Run git with a test identity.

    Args:
        directory: the checkout.
        *words: git's arguments.

    Returns:
        Its output.
    """
    identity = [
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "-c",
        "commit.gpgsign=false",
    ]
    return captured.run(["git", "-C", str(directory), *identity, *words]).stdout


def repo_pair(refuse: bool = False) -> pathlib.Path:
    """An origin and a worktree on ``worker/7`` with one commit of work.

    Args:
        refuse: whether the origin refuses every push.

    Returns:
        The worktree.
    """
    root = scratch.directory()
    origin, worktree = root / "origin.git", root / "wt"
    captured.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)])
    captured.run(["git", "clone", "-q", str(origin), str(worktree)])
    git(worktree, "commit", "-q", "--allow-empty", "-m", "init")
    git(worktree, "push", "-q", "origin", "HEAD:main")
    git(worktree, "checkout", "-q", "-b", "worker/7")
    (worktree / "f").write_text("x", encoding="utf-8")
    git(worktree, "add", "f")
    git(worktree, "commit", "-q", "-m", "work")
    if refuse:
        hook = origin / "hooks" / "pre-receive"
        hook.write_text(
            "#!/bin/sh\necho refused by the origin >&2; exit 1\n", encoding="utf-8"
        )
        hook.chmod(0o755)
    return worktree


def remote_head(worktree: pathlib.Path) -> str:
    """The origin's ``worker/7``.

    Args:
        worktree: the worktree.

    Returns:
        Its commit, or "" when it has none.
    """
    found = git(worktree, "ls-remote", "origin", "refs/heads/worker/7").split()
    return found[0] if found else ""


def ticket(repo: pathlib.Path, *paths: str) -> rulefiles.Ticket:
    """A ticket of a checkout, with a home of no user file.

    Args:
        repo: the checkout.
        *paths: the ticket's paths.

    Returns:
        The ticket.
    """
    return rulefiles.Ticket(checkout=repo, paths=list(paths), home=scratch.directory())
