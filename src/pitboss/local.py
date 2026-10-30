"""Work on this machine: stragglers and stale worktrees."""

import dataclasses
import enum
import os
import pathlib
import subprocess
from typing import Iterable, Iterator, Mapping, Sequence

from . import config, ghapi, parsing, shapes
from .running import Run, changed_files, git

_SKIPPED_DIRECTORIES = frozenset({".git", "node_modules"})
_DEPTH = 3


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Straggler:
    """A checkout with work that exists only on this machine.

    Attributes:
        path: the checkout.
        branch: its branch, or empty when detached.
        uncommitted: how many files are changed or untracked.
        unpushed: how many commits are on no remote branch.
        on_origin: whether its branch exists on ``origin``.
        last: its last commit, abbreviated.
    """

    path: pathlib.Path
    branch: str
    uncommitted: int
    unpushed: int
    on_origin: bool
    last: str


def checkouts(workspace: pathlib.Path) -> Sequence[pathlib.Path]:
    """The git checkouts directly under the workspace.

    Args:
        workspace: the directory.

    Returns:
        The checkouts, sorted.
    """
    return sorted(path for path in workspace.iterdir() if (path / ".git").exists())


def _repository_of(run: Run, checkout: pathlib.Path) -> str:
    try:
        found = git(
            run, checkout, "rev-parse", "--path-format=absolute", "--git-common-dir"
        )
    except subprocess.CalledProcessError:
        return ""
    return found.strip()


def fetch_each_repository(run: Run, paths: Iterable[pathlib.Path]) -> Sequence[str]:
    """Fetch ``origin`` once per repository (worktrees share their refs).

    Args:
        run: the runner.
        paths: the checkouts.

    Returns:
        The checkouts whose fetch failed, or whose repository git cannot read.
    """
    by_repository: dict[str, pathlib.Path] = {}
    failed = []
    for checkout in paths:
        common = _repository_of(run, checkout)
        if common:
            by_repository.setdefault(common, checkout)
        else:
            failed.append(str(checkout))
    for checkout in by_repository.values():
        try:
            git(run, checkout, "fetch", "-q", "origin")
        except subprocess.CalledProcessError:
            failed.append(str(checkout))
    return failed


def unpushed(run: Run, path: pathlib.Path) -> int:
    """Count the commits of HEAD that are on no remote branch.

    Args:
        run: the runner.
        path: the checkout.

    Returns:
        The count (none in a repository with no commits).
    """
    try:
        found = git(
            run, path, "rev-list", "--count", "HEAD", "--not", "--remotes=origin"
        )
    except subprocess.CalledProcessError:
        return 0
    return int(found.strip() or 0)


def uncommitted(run: Run, path: pathlib.Path) -> int:
    """Count the changed and untracked files.

    Args:
        run: the runner.
        path: the checkout.

    Returns:
        The count.
    """
    return changed_files(run, path)


def read_straggler(run: Run, path: pathlib.Path) -> Straggler | None:
    """Look at one checkout.

    Args:
        run: the runner.
        path: the checkout.

    Returns:
        A straggler, or None when everything in it is on GitHub.
    """
    changed, ahead = uncommitted(run, path), unpushed(run, path)
    if not changed and not ahead:
        return None
    branch = git(run, path, "branch", "--show-current").strip()
    remote = (
        git(run, path, "branch", "-r", "--list", f"origin/{branch}") if branch else ""
    )
    return Straggler(
        path=path,
        branch=branch,
        uncommitted=changed,
        unpushed=ahead,
        on_origin=bool(remote.strip()),
        last=git(run, path, "log", "-1", "--format=%h %cr %s").strip()[:60],
    )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Worktree:
    """A worktree of the main clone.

    Attributes:
        path: where it is.
        branch: its branch, or empty when detached.
        head: its tip.
    """

    path: pathlib.Path
    branch: str
    head: str


def parse_worktrees(porcelain: str) -> Sequence[Worktree]:
    """Parse ``git worktree list --porcelain``.

    Args:
        porcelain: the output.

    Returns:
        The worktrees.
    """
    found = []
    for block in porcelain.strip().split("\n\n"):
        fields = dict(line.partition(" ")[::2] for line in block.splitlines())
        if "worktree" in fields:
            found.append(
                Worktree(
                    path=pathlib.Path(fields["worktree"]),
                    branch=fields.get("branch", "").removeprefix("refs/heads/"),
                    head=fields.get("HEAD", ""),
                )
            )
    return found


def shallow_walk(
    path: pathlib.Path,
) -> Iterator[tuple[pathlib.Path, Sequence[str], Sequence[str]]]:
    """Walk three levels down, skipping ``.git`` and ``node_modules``.

    Args:
        path: the directory.

    Yields:
        Each directory, the names of its subdirectories and of its files.
    """
    base_depth = len(path.parts)
    for directory, subdirectories, files in os.walk(path):
        current = pathlib.Path(directory)
        yield current, tuple(subdirectories), tuple(files)
        deep = len(current.parts) - base_depth >= _DEPTH
        subdirectories[:] = (
            []
            if deep
            else [name for name in subdirectories if name not in _SKIPPED_DIRECTORIES]
        )


def modified(entry: pathlib.Path) -> float:
    """When an entry changed; a link is itself, not what it points at.

    Args:
        entry: the file, directory or link.

    Returns:
        Seconds since the epoch; 0 for an entry that is gone.
    """
    try:
        return entry.lstat().st_mtime
    except FileNotFoundError:
        return 0.0


def touched_since(path: pathlib.Path, cutoff: float) -> bool:
    """Whether anything in a checkout changed after ``cutoff``.

    File times, not the last commit: a new worktree's tip is an old commit.
    ``.git`` and ``node_modules`` are skipped; the walk stops three levels
    down.

    Args:
        path: the checkout.
        cutoff: a time, in seconds since the epoch.

    Returns:
        True when something is newer than ``cutoff``.
    """
    for current, _, files in shallow_walk(path):
        entries = [current, *(current / name for name in files)]
        if any(modified(entry) > cutoff for entry in entries):
            return True
    return False


class Reason(enum.Enum):
    """Why a worktree is stale.

    Attributes:
        MERGED: its PR merged.
        CLOSED: its PR was closed without merging.
        IN_BASE: it has no PR and its tip is in the base branch.
    """

    MERGED = "its PR merged"
    CLOSED = "its PR was closed"
    IN_BASE = "its tip is in the base branch"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Sweeper:
    """What deciding about worktrees needs.

    Attributes:
        run: the runner for reads.
        settings: the configuration.
        outcomes: each branch's PR outcome, newest PR first.
        cutoff: anything touched after this time is in use.
    """

    run: Run
    settings: config.Config
    outcomes: Mapping[str, shapes.Outcome]
    cutoff: float


def read_outcomes(
    github: ghapi.GitHub, repo: config.Repo
) -> Mapping[str, shapes.Outcome]:
    """What became of each branch's newest PR.

    Args:
        github: the API.
        repo: the repository.

    Returns:
        The outcome of each branch.
    """
    found: dict[str, shapes.Outcome] = {}
    listed = ghapi.pages(github, f"repos/{repo.slug}/pulls?state=all", parsing.outcomes)
    for outcome in listed:
        found.setdefault(outcome.branch, outcome)
    return found


def _in_use(sweeper: Sweeper, worktree: Worktree) -> bool:
    project = sweeper.settings.project
    return (
        worktree.path == project.main_clone
        or not worktree.path.is_relative_to(project.workspace)
        or not worktree.path.is_dir()
        or bool(uncommitted(sweeper.run, worktree.path))
        or bool(unpushed(sweeper.run, worktree.path))
        or touched_since(worktree.path, sweeper.cutoff)
    )


def in_base(run: Run, directory: pathlib.Path, revision: str, base: str) -> bool:
    """Whether a commit is in ``origin/<base>`` (as of the last fetch).

    Args:
        run: the runner.
        directory: a checkout of the repository.
        revision: the commit.
        base: the base branch.

    Returns:
        True when the base branch contains it.
    """
    contains = git(
        run,
        directory,
        "branch",
        "-r",
        "--contains",
        revision,
        "--list",
        f"origin/{base}",
    )
    return bool(contains.strip())


def stale_reason(sweeper: Sweeper, worktree: Worktree) -> Reason | None:
    """Decide whether a worktree is stale.

    It is stale only when all hold: it is not the main clone and is under
    the workspace; nothing is uncommitted; every commit is on a remote
    branch; nothing in it was touched since the cutoff; and its PR merged
    or was closed, or (with no PR) its tip is in the base branch. A
    worktree with an open PR is never stale.

    Args:
        sweeper: what the decision needs.
        worktree: the worktree.

    Returns:
        Why it is stale, or None when it is kept.
    """
    if _in_use(sweeper, worktree):
        return None
    outcome = sweeper.outcomes.get(worktree.branch) if worktree.branch else None
    if outcome is not None and not outcome.still_open:
        return Reason.MERGED if outcome.merged else Reason.CLOSED
    if outcome is None and in_base(
        sweeper.run,
        sweeper.settings.project.main_clone,
        worktree.head,
        sweeper.settings.project.base_branch,
    ):
        return Reason.IN_BASE
    return None
