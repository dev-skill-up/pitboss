"""One look at the dead checkouts and scratch: finished work still on disk."""

import dataclasses
import functools
import pathlib
import subprocess
from typing import Callable, Iterable, Mapping, Sequence

from . import concurrently, config, dead, local, shapes
from .dead import Kept
from .running import git

Decide = Callable[
    [dead.Look, Mapping[str, Mapping[str, shapes.Outcome]], "Checkout"],
    local.Reason | None,
]


def slug_of(url: str) -> str:
    """The ``owner/name`` a remote URL names.

    Args:
        url: ``https://host/owner/name.git`` or ``git@host:owner/name``.

    Returns:
        The slug, or empty when the URL has no owner.
    """
    parts = url.strip().removesuffix(".git").replace(":", "/").split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 and parts[-2] else ""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Checkout:
    """A git checkout under the workspace.

    Attributes:
        path: where.
        branch: its branch, or empty when detached.
        slug: its repository, or empty when unknown.
        common: its repository's git directory.
    """

    path: pathlib.Path
    branch: str
    slug: str
    common: pathlib.Path


def read_checkout(look: dead.Look, path: pathlib.Path) -> Checkout:
    """Look at one checkout.

    Args:
        look: what to look at.
        path: the checkout.

    Returns:
        Its facts; a checkout of the main clone's repository is the project's.
    """
    run, project = look.run, look.settings.project
    found = git(run, path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    common = pathlib.Path(found.strip()).resolve()
    if common == (project.main_clone / ".git").resolve():
        slug = project.repo.slug
    else:
        try:
            url = git(run, path, "config", "--get", "remote.origin.url")
        except subprocess.CalledProcessError:
            url = ""
        slug = slug_of(url)
    branch = git(run, path, "branch", "--show-current").strip()
    return Checkout(path=path, branch=branch, slug=slug, common=common)


def pressure_reason(
    look: dead.Look,
    outcomes: Mapping[str, Mapping[str, shapes.Outcome]],
    each: Checkout,
) -> local.Reason | None:
    """Why a checkout is dead under disk pressure (keyword: auto-clean).

    A checkout of a repository with no open PR is dead too, whatever its branch.

    Args:
        look: what to look at.
        outcomes: each repository's branch outcomes.
        each: the checkout.

    Returns:
        The reason, or None when the checkout is kept.
    """
    reason = checkout_reason(look, outcomes, each)
    known = outcomes.get(each.slug)
    if reason is not None or known is None:
        return reason
    if each.branch and each.branch != look.settings.project.base_branch:
        return None if opened(known, each.branch) else local.Reason.NO_OPEN_PR
    quiet = not any(one.still_open for one in known.values())
    return local.Reason.QUIET_REPOSITORY if quiet else None


def opened(known: Mapping[str, shapes.Outcome], branch: str) -> bool:
    """Whether a branch has an open PR.

    Args:
        known: the branch outcomes of a repository.
        branch: the branch.

    Returns:
        True when its newest PR is open.
    """
    return branch in known and known[branch].still_open


def explain_keeping(
    look: dead.Look,
    outcomes: Mapping[str, Mapping[str, shapes.Outcome]],
    each: Checkout,
) -> str:
    """Why a checkout that is not dead is kept.

    Args:
        look: what to look at.
        outcomes: each repository's branch outcomes.
        each: the checkout.

    Returns:
        The reason, in words.
    """
    known = outcomes.get(each.slug)
    if not each.slug:
        return "it has no remote origin to ask about its PRs"
    if known is None:
        return f"the PRs of {each.slug} could not be read"
    if not each.branch:
        return "detached: a persistent checkout"
    if each.branch == look.settings.project.base_branch:
        return "on the base branch: a persistent checkout"
    if opened(known, each.branch):
        return "its branch has an open PR"
    return "its branch is not merged or closed"


def checkout_reason(
    look: dead.Look,
    outcomes: Mapping[str, Mapping[str, shapes.Outcome]],
    each: Checkout,
) -> local.Reason | None:
    """Why a checkout is dead.

    A checkout on the base branch, or detached, is never dead: it is a
    persistent checkout.

    Args:
        look: what to look at.
        outcomes: each repository's branch outcomes.
        each: the checkout.

    Returns:
        The reason, or None when the checkout is kept.
    """
    base = look.settings.project.base_branch
    if not each.branch or each.branch == base:
        return None
    newest = outcomes.get(each.slug, {}).get(each.branch)
    if newest is not None and not newest.still_open:
        return local.Reason.MERGED if newest.merged else local.Reason.CLOSED
    if newest is None and local.in_base(look.run, each.path, "HEAD", base):
        return local.Reason.IN_BASE
    return None


def _outcomes(
    look: dead.Look, slugs: Iterable[str]
) -> Mapping[str, Mapping[str, shapes.Outcome]]:
    # A clone of a repository the configuration does not name is asked about
    # too: its branches' PRs decide it as much as any other's.
    owner = look.settings.project.repo.owner
    repos = {repo.slug: repo for repo in config.repositories(look.settings)}
    wanted = sorted({slug for slug in slugs if slug})

    def attempt(slug: str) -> Mapping[str, shapes.Outcome] | None:
        repo = repos.get(slug) or config.parse_repo(slug, owner)
        try:
            return local.read_outcomes(look.github, repo)
        except subprocess.CalledProcessError:
            return None

    read = concurrently.each(attempt, wanted)
    return {slug: found for slug, found in zip(wanted, read) if found is not None}


def _linked(each: Checkout) -> pathlib.Path | None:
    own = (each.path / ".git").resolve()
    return None if each.common == own else each.common


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Judging:
    """How a checkout is judged.

    Attributes:
        decided: why a checkout is dead, or None.
        explained: why a checkout that is not dead is kept.
    """

    decided: Callable[[Checkout], local.Reason | None]
    explained: Callable[[Checkout], str]


def _judged(
    judging: Judging, look: dead.Look, cutoff: float, each: Checkout
) -> dead.Candidate | Kept:
    reason = judging.decided(each)
    if reason is None:
        return Kept(path=each.path, why=judging.explained(each))
    # Only the marker of a merged checkout expires (pitboss#194).
    merged = reason in local.MERGED_WORK
    eyes = look if merged else dataclasses.replace(look, marker_expiry=0.0)
    held, kept, found = dead.verdict(eyes, each.path, cutoff)
    if held:
        return Kept(path=each.path, why=held, size=found.size)
    made = dead.Candidate(
        path=each.path, size=found.size, reason=reason.value, kept=kept
    )
    return dataclasses.replace(made, prune=_linked(each))


def _fetched(
    look: dead.Look, read: Sequence[Checkout]
) -> tuple[Sequence[Checkout], Sequence[str]]:
    firsts = {each.common: each.path for each in reversed(read)}
    failed = local.fetch_each_repository(look.run, firsts.values())
    return [e for e in read if str(firsts[e.common]) not in failed], sorted(failed)


def _read(
    look: dead.Look, paths: Iterable[pathlib.Path]
) -> tuple[Sequence[Checkout], Sequence[pathlib.Path]]:
    wanted = list(paths)

    def attempt(path: pathlib.Path) -> Checkout | None:
        try:
            return read_checkout(look, path)
        except subprocess.CalledProcessError:
            return None

    attempted = concurrently.each(attempt, wanted)
    read = [each for each in attempted if each is not None]
    unreadable = [path for path, each in zip(wanted, attempted) if each is None]
    return read, unreadable


def _unreadable(
    look: dead.Look, cutoff: float, each: pathlib.Path
) -> dead.Candidate | Kept:
    # A checkout git cannot read is kept, never removed.
    held, seen = dead.hold(look, each, cutoff)
    if held:
        return Kept(path=each, why=held, size=seen.size)
    return dead.Candidate(
        path=each,
        size=seen.size,
        reason="a checkout git cannot read",
        kept=f"git cannot read {each}",
    )


def plain_directories(workspace: pathlib.Path) -> Sequence[Kept]:
    """The directories of the workspace that are not git checkouts.

    They are never judged; a hidden one is not named.

    Args:
        workspace: the directory.

    Returns:
        A ``Kept`` for each, sorted.
    """
    return [
        Kept(path=path, why="not a git checkout")
        for path in sorted(workspace.iterdir())
        if path.is_dir()
        and not path.is_symlink()
        and not path.name.startswith(".")
        and not (path / ".git").exists()
    ]


def _judging(
    look: dead.Look,
    decide: Decide,
    outcomes: Mapping[str, Mapping[str, shapes.Outcome]],
) -> Judging:
    return Judging(
        decided=functools.partial(decide, look, outcomes),
        explained=functools.partial(explain_keeping, look, outcomes),
    )


def _checkout_paths(look: dead.Look) -> Sequence[pathlib.Path]:
    found = local.checkouts(look.settings.project.workspace)
    return [path for path in found if not path.is_symlink()]


def _skipped(read: Sequence[Checkout], fetched: Sequence[Checkout]) -> Sequence[Kept]:
    why = "its repository could not be fetched"
    return [Kept(path=each.path, why=why) for each in read if each not in fetched]


def dead_checkouts(
    look: dead.Look, cutoff: float, decide: Decide = checkout_reason
) -> tuple[Sequence[dead.Candidate | Kept], Sequence[str]]:
    """The checkouts under the workspace, each dead or kept.

    A link is never a checkout: it is not judged by what it points at.

    Args:
        look: what to look at and keep.
        cutoff: anything changed after this time is in use.
        decide: why a checkout is dead: ``checkout_reason``, or
            ``pressure_reason`` under disk pressure (keyword: auto-clean).

    Returns:
        A candidate for each dead checkout, a ``Kept`` (with why) for each that
        is not dead or is live or in use, and the checkouts whose fetch failed.
    """
    read, unreadable = _read(look, _checkout_paths(look))
    fetched, failed = _fetched(look, read)
    outcomes = _outcomes(look, {each.slug for each in fetched})
    judging = _judging(look, decide, outcomes)
    judged = concurrently.each(
        lambda each: _judged(judging, look, cutoff, each), fetched
    )
    plain = dataclasses.replace(look, marker_expiry=0.0)
    found = [
        *(_unreadable(plain, cutoff, each) for each in unreadable),
        *judged,
        *_skipped(read, fetched),
    ]
    return found, failed


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Findings:
    """What a look at the machine found.

    Attributes:
        candidates: the dead paths, largest first.
        unfetched: checkouts whose repository could not be fetched; their
            repository's checkouts are not judged.
        kept: the directories of the workspace that are not dead or are live or
            in use, each with why; the dead ones that are not safe are
            candidates with a reason.
    """

    candidates: Sequence[dead.Candidate]
    unfetched: Sequence[str]
    kept: Sequence[Kept] = ()


def scan(look: dead.Look, now: float, decide: Decide = checkout_reason) -> Findings:
    """Look at the workspace, the scratch directories and the root files.

    Args:
        look: what to look at and keep.
        now: seconds since the epoch.
        decide: why a checkout is dead.

    Returns:
        The dead paths (checkouts, scratch and the root files), the
        checkouts that could not be fetched, and the directories of the
        workspace that are kept, each with why.
    """
    cutoff = now - look.settings.idle_hours * 3600
    found, unfetched = dead_checkouts(look, cutoff, decide)
    # Only a merged checkout's marker expires, not a scratch entry's (pitboss#194).
    plain = dataclasses.replace(look, marker_expiry=0.0)
    scratch = dead.dead_scratch(plain, cutoff)
    files = dead.dead_root_files(plain, cutoff)
    checkouts = [each for each in found if isinstance(each, dead.Candidate)]
    kept = [each for each in found if isinstance(each, Kept)]
    return Findings(
        candidates=dead.ordered([*checkouts, *scratch, *files]),
        unfetched=unfetched,
        kept=[*kept, *plain_directories(look.settings.project.workspace)],
    )
