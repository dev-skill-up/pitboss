"""Whether what is in a path exists anywhere else.

A path is safe to remove when nothing in it exists only on this machine: every
git checkout in it has its commits on a remote branch and no changed tracked
file. Where the checkout's repository is inside the path (a standalone clone
loses its other branches and its stash with it) every ref is looked at, not
only HEAD (keyword: clean-container, ``rules.md``, "Checkouts and disk"). What
cannot be read is not safe.
"""

import itertools
import pathlib
import subprocess
from typing import Sequence

from . import survey
from .running import Run, changed_files, git


def has_head(run: Run, root: pathlib.Path) -> bool:
    """Whether HEAD names a commit (a repository with none has nothing to lose).

    Args:
        run: the runner.
        root: the checkout.

    Returns:
        False for a branch that has no commit yet.

    Raises:
        subprocess.CalledProcessError: for any other failure of git.
    """
    try:
        git(run, root, "rev-parse", "--verify", "--quiet", "HEAD")
    except subprocess.CalledProcessError as error:
        if error.returncode != 1:
            raise
        return False
    return True


def count_commits(run: Run, root: pathlib.Path, scope: str) -> int:
    """Count the commits of some refs that are on no branch of ``origin``.

    Args:
        run: the runner.
        root: the checkout.
        scope: the refs: ``HEAD`` or ``--all``.

    Returns:
        The count.
    """
    found = git(run, root, "rev-list", "--count", scope, "--not", "--remotes=origin")
    return int(found.strip())


def in_head(run: Run, root: pathlib.Path) -> int:
    """Count the commits of HEAD that are on no branch of ``origin``.

    A linked worktree goes without its repository, which keeps the other refs.

    Args:
        run: the runner.
        root: the checkout.

    Returns:
        The count; 0 for a branch with no commit yet.
    """
    return count_commits(run, root, "HEAD") if has_head(run, root) else 0


def in_every_ref(run: Run, root: pathlib.Path) -> int:
    """Count the commits of every ref (branches, tags, the stash) on no remote.

    A standalone clone goes with all of them.

    Args:
        run: the runner.
        root: the checkout.

    Returns:
        The count.
    """
    return count_commits(run, root, "--all")


def tracked_changes(run: Run, root: pathlib.Path) -> int:
    """Count the changed tracked files (untracked files are not counted).

    Args:
        run: the runner.
        root: the checkout.

    Returns:
        The count.
    """
    return changed_files(run, root, "--untracked-files=no")


def is_toplevel(run: Run, root: pathlib.Path) -> bool:
    """Whether git reads the directory as a checkout of its own.

    A broken ``.git`` falls through to the repository above, if there is one.

    Args:
        run: the runner.
        root: the directory.

    Returns:
        True when git's top level is the directory.
    """
    top = git(run, root, "rev-parse", "--show-toplevel")
    return top.strip() != "" and pathlib.Path(top.strip()).resolve() == root.resolve()


def goes_with(run: Run, root: pathlib.Path, inside: pathlib.Path) -> bool:
    """Whether a checkout's repository is inside the path that would be removed.

    Args:
        run: the runner.
        root: the checkout.
        inside: the path.

    Returns:
        True when the repository's git directory is in the path.
    """
    found = git(run, root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return pathlib.Path(found.strip()).resolve().is_relative_to(inside.resolve())


def losses(run: Run, root: pathlib.Path, inside: pathlib.Path) -> Sequence[int]:
    """What would be lost of a checkout.

    Args:
        run: the runner.
        root: the checkout.
        inside: the path that would be removed.

    Returns:
        The commits on no remote branch (of every ref when the repository goes
        too, else of HEAD), and the changed tracked files.
    """
    ahead = in_every_ref if goes_with(run, root, inside) else in_head
    return [ahead(run, root), tracked_changes(run, root)]


def read(run: Run, root: pathlib.Path, inside: pathlib.Path) -> Sequence[int] | None:
    """What would be lost of a checkout, or None when git cannot say.

    Args:
        run: the runner.
        root: the checkout.
        inside: the path that would be removed.

    Returns:
        The commits on no remote branch and the changed tracked files; None
        when git fails or does not read the directory as a checkout of its own.
    """
    try:
        return losses(run, root, inside) if is_toplevel(run, root) else None
    except subprocess.CalledProcessError:
        return None


def judge(run: Run, root: pathlib.Path, inside: pathlib.Path) -> str:
    """Why a checkout in a path is not safe to remove.

    Args:
        run: the runner.
        root: the checkout.
        inside: the path that would be removed.

    Returns:
        The reason, or empty when everything in the checkout is on a remote
        branch and no tracked file is changed.
    """
    found = read(run, root, inside)
    if found is None:
        return f"git cannot read {root}"
    ahead, changed = found
    if ahead:
        return f"{ahead} commits on no remote branch in {root}"
    if changed:
        return f"{changed} changed tracked files in {root}"
    return ""


def trouble(run: Run, path: pathlib.Path, found: survey.Survey) -> str:
    """Why a path is not safe to remove: work that exists only here, or unseen.

    Args:
        run: the runner.
        path: the path.
        found: what a walk of it found.

    Returns:
        The first reason, or empty when it is safe.
    """
    reasons = itertools.chain(
        (f"cannot look at {each}" for each in found.unreadable),
        (f"mount point {each}" for each in found.mounts),
        (f"bare git repository {each}" for each in found.bare),
        (judge(run, each, path) for each in found.repositories),
    )
    return next((reason for reason in reasons if reason), "")
