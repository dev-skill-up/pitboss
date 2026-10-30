"""One look at the dead checkouts and scratch: finished work still on disk."""

import dataclasses
import pathlib
import subprocess
from typing import Iterable, Mapping, Sequence

from . import config, dead, local, shapes
from .running import git


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


def _fetched(
    look: dead.Look, read: Sequence[Checkout]
) -> tuple[Sequence[Checkout], Sequence[str]]:
    firsts = {each.common: each.path for each in reversed(read)}
    failed = local.fetch_each_repository(look.run, firsts.values())
    return [e for e in read if str(firsts[e.common]) not in failed], sorted(failed)


def dead_checkouts(
    look: dead.Look, cutoff: float
) -> tuple[Sequence[dead.Candidate], Sequence[str]]:
    """The checkouts under the workspace that are dead.

    Args:
        look: what to look at and keep.
        cutoff: anything touched after this time is in use.

    Returns:
        The candidates and the checkouts whose fetch failed.
    """
    read = [
        read_checkout(look, path)
        for path in local.checkouts(look.settings.project.workspace)
    ]
    fetched, failed = _fetched(look, read)
    outcomes = _outcomes(look, {each.slug for each in fetched})
    found = []
    for each in fetched:
        reason = checkout_reason(look, outcomes, each)
        if reason is None or dead.is_live(each.path, look):
            continue
        if not dead.touched(each.path, cutoff):
            found.append(dead.make(look.run, each.path, reason.value, _linked(each)))
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


def scan(look: dead.Look, now: float) -> Findings:
    """Look at the workspace and the scratch directories.

    Args:
        look: what to look at and keep.
        now: seconds since the epoch.

    Returns:
        The dead paths and the checkouts that could not be fetched.
    """
    cutoff = now - look.settings.idle_hours * 3600
    checkouts, unfetched = dead_checkouts(look, cutoff)
    scratch = dead.dead_scratch(look, cutoff)
    return Findings(
        candidates=dead.ordered([*checkouts, *scratch]), unfetched=unfetched
    )
