"""Where a PR's hand-backs are read from (keyword: standing).

The record ``hand-back-check`` wrote is kept in the project's main clone for the
PR's repository and branch, and in the worktree's git directory (the older form). A
hand-back is required of every PR but a relock PR, whatever worktree exists
(pitboss#513); when git fails the answer is unknown, and the PR has no hand-back.
"""

import pathlib
import subprocess
from typing import Callable

from . import config, handbackrecord, handbacks, local, relock, running

Asks = Callable[[config.Repo, str], handbacks.HandedBack]


def worktree_found(
    run: running.Run, clone: pathlib.Path, branch: str
) -> pathlib.Path | None:
    """The git directory of the worktree of a branch; a git failure is raised.

    Args:
        run: the runner.
        clone: the main clone, whose worktrees are listed.
        branch: the branch.

    Returns:
        The worktree's git directory; None when git answered and no worktree
        holds the branch; a failed or unrunnable git raises (CalledProcessError,
        OSError) and is no answer.
    """
    listed = local.parse_worktrees(
        running.git(run, clone, "worktree", "list", "--porcelain")
    )
    paths = [each.path for each in listed if each.branch == branch]
    if not paths:
        return None
    return pathlib.Path(
        running.git(run, paths[0], "rev-parse", "--absolute-git-dir").strip()
    )


def worktree_directory(
    run: running.Run, clone: pathlib.Path, branch: str
) -> pathlib.Path | None:
    """The git directory of the worktree of a branch.

    Args:
        run: the runner.
        clone: the main clone, whose worktrees are listed.
        branch: the branch.

    Returns:
        The worktree's git directory; None when no worktree holds the branch or git
        failed.
    """
    try:
        return worktree_found(run, clone, branch)
    except (subprocess.CalledProcessError, OSError):
        return None


def held(
    ask: Asks, repo: config.Repo, branch: str, prefix: str
) -> handbacks.HandedBack:
    """What a PR's branch handed back, with no hand-back owed only for a relock PR.

    The keyword is durable-record (pitboss#513): a PR is not freed of a hand-back
    because no worktree holds its branch, only because it is a relock PR, which
    no worker writes.

    Args:
        ask: ``asker``'s function.
        repo: the PR's repository.
        branch: the PR's head branch.
        prefix: the head branch prefix of a relock PR.

    Returns:
        ``handbacks.NOT_REQUIRED`` for a relock PR, else what ``ask`` reads.
    """
    if relock.is_relock(branch, prefix):
        return handbacks.NOT_REQUIRED
    return ask(repo, branch)


def asker(run: running.Run, settings: config.Config) -> Asks:
    """The function that reads what was handed back for a branch.

    Args:
        run: the runner.
        settings: the configuration.

    Returns:
        A function from a PR's repository and head branch to what was recorded.
    """
    clone = settings.project.main_clone

    def ask(repo: config.Repo, branch: str) -> handbacks.HandedBack:
        try:
            directory = worktree_found(run, clone, branch)
            common = pathlib.Path(
                running.git(run, clone, "rev-parse", "--absolute-git-dir").strip()
            )
        except (subprocess.CalledProcessError, OSError):
            # git failed: no worker is known not to hold the PR, so none handed back
            return handbacks.HandedBack(required=True, states=frozenset())
        # keyword: durable-record: a hand-back is required whatever worktree exists
        found = handbackrecord.states(handbackrecord.kept(common, repo.slug, branch))
        older = frozenset() if directory is None else handbackrecord.states(directory)
        return handbacks.HandedBack(required=True, states=found | older)

    return ask
