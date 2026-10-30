"""Work on this machine: stragglers and stale worktrees."""

import dataclasses
import enum
import pathlib
import subprocess
from typing import Iterable, Mapping, Sequence

from . import config, ghapi, parsing, shapes
from .running import Run, changed_files, git


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


def orphaned(run: Run, checkout: pathlib.Path) -> bool:
    """Whether git cannot read a checkout (keyword: orphaned-checkout).

    A worktree whose main checkout was removed keeps its directory and a
    ``.git`` file that points at a gitdir that is gone; every git command in it
    exits 128.

    Args:
        run: the runner.
        checkout: the checkout.

    Returns:
        True when git cannot read it.
    """
    return not _repository_of(run, checkout)


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


class Reason(enum.Enum):
    """Why a worktree is finished.

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
    """

    run: Run
    settings: config.Config
    outcomes: Mapping[str, shapes.Outcome]


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


def _outside(sweeper: Sweeper, worktree: Worktree) -> bool:
    project = sweeper.settings.project
    return (
        worktree.path == project.main_clone
        or not worktree.path.is_relative_to(project.workspace)
        or not worktree.path.is_dir()
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


def finished_reason(sweeper: Sweeper, worktree: Worktree) -> Reason | None:
    """Decide whether a worktree's work is finished and on GitHub.

    It is finished only when it is not the main clone, lies under the
    workspace, and its PR merged or was closed, or (with no PR) its tip is in
    the base branch. A worktree with an open PR is never finished. Whether it
    may be removed is a second question, the one safety test of
    ``dead.verdict`` (keyword: clean-worktrees, ``rules.md``, "Checkouts and
    disk").

    Args:
        sweeper: what the decision needs.
        worktree: the worktree.

    Returns:
        Why it is finished, or None when it is not.
    """
    if _outside(sweeper, worktree):
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
