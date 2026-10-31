"""One look at the dead checkouts and scratch: finished work still on disk."""

import dataclasses
import functools
import pathlib
import subprocess
from typing import Callable, Iterable, Mapping, Sequence

from . import config, dead, local, shapes
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
    if reason is None and known is not None:
        quiet = not any(one.still_open for one in known.values())
        return local.Reason.QUIET_REPOSITORY if quiet else None
    return reason


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
    repos = {repo.slug: repo for repo in config.repositories(look.settings)}
    return {
        slug: local.read_outcomes(look.github, repos[slug])
        for slug in slugs
        if slug in repos
    }


def _linked(each: Checkout) -> pathlib.Path | None:
    own = (each.path / ".git").resolve()
    return None if each.common == own else each.common


def _judged(
    decided: Callable[[Checkout], local.Reason | None],
    look: dead.Look,
    cutoff: float,
    each: Checkout,
) -> dead.Candidate | None:
    reason = decided(each)
    if reason is None:
        return None
    made = dead.consider(look, each.path, reason.value, cutoff)
    return made and dataclasses.replace(made, prune=_linked(each))


def _fetched(
    look: dead.Look, read: Sequence[Checkout]
) -> tuple[Sequence[Checkout], Sequence[str]]:
    firsts = {each.common: each.path for each in reversed(read)}
    failed = local.fetch_each_repository(look.run, firsts.values())
    return [e for e in read if str(firsts[e.common]) not in failed], sorted(failed)


def _read(
    look: dead.Look, paths: Iterable[pathlib.Path]
) -> tuple[Sequence[Checkout], Sequence[pathlib.Path]]:
    read: list[Checkout] = []
    unreadable: list[pathlib.Path] = []
    for each in paths:
        try:
            read.append(read_checkout(look, each))
        except subprocess.CalledProcessError:
            unreadable.append(each)
    return read, unreadable


def unreadable_checkouts(
    look: dead.Look, cutoff: float, paths: Iterable[pathlib.Path]
) -> Sequence[dead.Candidate]:
    """The checkouts whose git directory git cannot read: kept, never removed.

    Args:
        look: what to look at and keep.
        cutoff: anything changed after this time is in use.
        paths: the checkouts.

    Returns:
        A kept candidate for each that is not live or in use.
    """
    reason = "a checkout git cannot read"
    made = dead.present(dead.consider(look, each, reason, cutoff) for each in paths)
    return [
        dataclasses.replace(each, kept=each.kept or f"git cannot read {each.path}")
        for each in made
    ]


def dead_checkouts(
    look: dead.Look, cutoff: float, decide: Decide = checkout_reason
) -> tuple[Sequence[dead.Candidate], Sequence[str]]:
    """The checkouts under the workspace that are dead.

    A link is never a checkout: it is not judged by what it points at.

    Args:
        look: what to look at and keep.
        cutoff: anything changed after this time is in use.
        decide: why a checkout is dead: ``checkout_reason``, or
            ``pressure_reason`` under disk pressure (keyword: auto-clean).

    Returns:
        The candidates and the checkouts whose fetch failed.
    """
    paths = [
        path
        for path in local.checkouts(look.settings.project.workspace)
        if not path.is_symlink()
    ]
    read, unreadable = _read(look, paths)
    fetched, failed = _fetched(look, read)
    outcomes = _outcomes(look, {each.slug for each in fetched})
    judging = functools.partial(decide, look, outcomes)
    judged = dead.present(_judged(judging, look, cutoff, each) for each in fetched)
    found = [*unreadable_checkouts(look, cutoff, unreadable), *judged]
    return found, failed


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Findings:
    """What a look at the machine found.

    Attributes:
        candidates: the dead paths, largest first.
        unfetched: checkouts whose repository could not be fetched; their
            repository's checkouts are not judged.
    """

    candidates: Sequence[dead.Candidate]
    unfetched: Sequence[str]


def scan(look: dead.Look, now: float, decide: Decide = checkout_reason) -> Findings:
    """Look at the workspace, the scratch directories and the root files.

    Args:
        look: what to look at and keep.
        now: seconds since the epoch.
        decide: why a checkout is dead.

    Returns:
        The dead paths (checkouts, scratch and the root files) and the
        checkouts that could not be fetched.
    """
    cutoff = now - look.settings.idle_hours * 3600
    checkouts, unfetched = dead_checkouts(look, cutoff, decide)
    scratch = dead.dead_scratch(look, cutoff)
    files = dead.dead_root_files(look, cutoff)
    return Findings(
        candidates=dead.ordered([*checkouts, *scratch, *files]),
        unfetched=unfetched,
    )
