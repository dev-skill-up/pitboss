"""One look at the dead checkouts and scratch: finished work still on disk."""

import dataclasses
import functools
import pathlib
import subprocess
from typing import AbstractSet, Callable, Iterable, Mapping, Sequence

from . import concurrently, dead, local, registered, shapes, ticketclosed
from .outcomes import outcomes_of
from .dead import Kept
from .running import Run, git

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
        head: its tip, or empty when it has no commit.
    """

    path: pathlib.Path
    branch: str
    slug: str
    common: pathlib.Path
    head: str = ""


def git_or_empty(run: Run, path: pathlib.Path, *words: str) -> str:
    """The output of a git read, empty when git fails.

    Args:
        run: the runner for reads.
        path: the checkout.
        *words: the git arguments.

    Returns:
        The output, or empty.
    """
    try:
        return git(run, path, *words)
    except subprocess.CalledProcessError:
        return ""


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
        slug = slug_of(git_or_empty(run, path, "config", "--get", "remote.origin.url"))
    branch = git(run, path, "branch", "--show-current").strip()
    head = git_or_empty(run, path, "rev-parse", "HEAD").strip()
    return Checkout(path=path, branch=branch, slug=slug, common=common, head=head)


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
    return "its branch is not merged or closed, and its name is no closed ticket's"


def checkout_reason(
    look: dead.Look,
    outcomes: Mapping[str, Mapping[str, shapes.Outcome]],
    each: Checkout,
) -> local.Reason | None:
    """Why a checkout is dead.

    A checkout on the base branch, or detached, is never dead: it is a
    persistent checkout. One whose branch has no PR is dead when its tip is in
    the base branch or a number in its name or branch is a closed ticket.

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
    if newest is not None:
        return None
    if local.in_base(look.run, each.path, "HEAD", base):
        return local.Reason.IN_BASE
    names = (each.path.name, each.branch)
    closed = each.slug and ticketclosed.closed_ticket(look.github, each.slug, names)
    return local.Reason.TICKET_CLOSED if closed else None


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
    linked = _linked(each)
    return dataclasses.replace(made, prune=linked, head=each.head if linked else "")


def _firsts(read: Sequence[Checkout]) -> registered.Firsts:
    return {each.common: each.path for each in reversed(read)}


def _fetched(
    look: dead.Look, read: Sequence[Checkout]
) -> tuple[Sequence[Checkout], Sequence[str]]:
    firsts = _firsts(read)
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


def _every(
    look: dead.Look,
) -> tuple[Sequence[Checkout], Sequence[pathlib.Path]]:
    # The checkouts directly under the workspace, and the worktrees git lists
    # for their repositories wherever under the workspace (pitboss#348).
    direct, lost = _read(look, _checkout_paths(look))
    known = {each.path.resolve() for each in direct}
    workspace = look.settings.project.workspace
    more = registered.under_workspace(look.run, workspace, _firsts(direct), known)
    deeper, lost_deeper = _read(look, more)
    return [*direct, *deeper], [*lost, *lost_deeper]


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
    read, unreadable = _every(look)
    fetched, failed = _fetched(look, read)
    slugs = {each.slug for each in fetched}
    outcomes = outcomes_of(look.github, look.settings, slugs)
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
        places: the directories under the workspace that hold a dead checkout,
            which are not otherwise a place ``clean-container`` removes from.
        tickets: the numbers in the names of the dead checkouts.
    """

    candidates: Sequence[dead.Candidate]
    unfetched: Sequence[str]
    kept: Sequence[Kept] = ()
    places: AbstractSet[pathlib.Path] = frozenset()
    tickets: Sequence[int] = ()


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
    elsewhere = dead.dead_elsewhere(plain, cutoff)
    checkouts = [each for each in found if isinstance(each, dead.Candidate)]
    kept = [each for each in found if isinstance(each, Kept)]
    workspace = look.settings.project.workspace
    places, tickets = ticketclosed.where(workspace, [e.path for e in checkouts])
    return Findings(
        candidates=dead.ordered([*checkouts, *elsewhere]),
        unfetched=unfetched,
        kept=[*kept, *dead.plain_directories(workspace)],
        places=places,
        tickets=tickets,
    )
