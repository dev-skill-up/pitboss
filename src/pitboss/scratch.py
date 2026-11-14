"""Scratch PRs of finished runs: flagged, then closed with their branches.

A scratch repository (``[scratch]``, keyword: scratch) is where a run tries
something on a real GitHub (a workflow that only runs from the default branch,
a fixture). When the run is done its PR is closed and its branch deleted, and
nothing is left behind; the PRs named in ``keep`` are fixtures and are never
touched. A scratch run reuses the fixed branch names of ``branches``, because a
branch delete is blocked in an agent session.
"""

import dataclasses
import datetime
import subprocess
from typing import AbstractSet, Sequence

from . import checkoutcome, ghapi, parsing, pullparse, scratchconfig, shapes
from .markers import Marker
from .running import Run

GRACE_MINUTES = 10


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Source:
    """What reading the scratch repositories needs.

    Attributes:
        github: the API.
        scratch: the settings.
        now: the time now.
    """

    github: ghapi.GitHub
    scratch: scratchconfig.Scratch
    now: datetime.datetime


def source_of(
    run: Run, scratch: scratchconfig.Scratch, now: datetime.datetime
) -> Source:
    """A source whose changes really run (a sweep that cleans, ``clean``).

    Args:
        run: the runner reads and changes both go through.
        scratch: the settings.
        now: the time now.

    Returns:
        The source.
    """
    github = ghapi.GitHub(run=run, mutate=run)
    return Source(github=github, scratch=scratch, now=now)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Entry:
    """An open PR of a scratch repository.

    Attributes:
        slug: the scratch repository's ``owner/name``.
        pull: the PR.
        kept: whether it is a fixture that stays open.
        finished: whether its head's workflow runs have all finished (a head
            with no run is finished once the PR is older than the grace
            period); false for a fixture, which is never read.
        off_branch: whether its head branch is not one of the run branches.
    """

    slug: str
    pull: shapes.Pull
    kept: bool
    finished: bool
    off_branch: bool


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Look:
    """What the scratch repositories hold now.

    Attributes:
        entries: every open PR of the repositories that could be read.
        unreadable: a line for each repository that could not be read.
    """

    entries: Sequence[Entry]
    unreadable: Sequence[str]


def reference(entry: Entry) -> str:
    """The PR's ``owner/name#number``.

    Args:
        entry: the PR.

    Returns:
        The reference.
    """
    return f"{entry.slug}#{entry.pull.number}"


def _finished(source: Source, slug: str, pull: shapes.Pull) -> bool:
    runs = ghapi.pages(
        source.github,
        f"repos/{slug}/actions/runs?head_sha={pull.head.sha}",
        parsing.workflow_runs,
    )
    if runs:
        return checkoutcome.all_finished(runs)
    opened = datetime.datetime.fromisoformat(pull.created_at)
    return (source.now - opened) >= datetime.timedelta(minutes=GRACE_MINUTES)


def _entry(source: Source, slug: str, pull: shapes.Pull) -> Entry:
    kept = f"{slug}#{pull.number}" in source.scratch.keep
    branches = source.scratch.branches
    return Entry(
        slug=slug,
        pull=pull,
        kept=kept,
        finished=not kept and _finished(source, slug, pull),
        off_branch=not kept and bool(branches) and pull.head.branch not in branches,
    )


def read(source: Source) -> Look:
    """Read the open PRs of every scratch repository.

    Args:
        source: what reading needs.

    Returns:
        The PRs, by repository in configured order, then as GitHub lists them;
        a repository whose API call failed as a line.
    """
    entries: list[Entry] = []
    unreadable: list[str] = []
    for slug in source.scratch.repositories:
        try:
            path = f"repos/{slug}/pulls?state=open"
            found = ghapi.pages(source.github, path, pullparse.open_pulls)
            entries.extend(_entry(source, slug, pull) for pull in found)
        except subprocess.CalledProcessError as error:
            unreadable.append(
                f"{Marker.UNREADABLE.text} {slug}: {ghapi.status_of(error)}: give"
                " the session access or take it out of [scratch]; skipped"
            )
    return Look(entries=entries, unreadable=unreadable)


def finished_line(entry: Entry) -> Sequence[str]:
    """The line that flags a PR whose run is done.

    Args:
        entry: the PR.

    Returns:
        The line; none while the run goes, and for a fixture.
    """
    if not entry.finished:
        return []
    return [
        f"{Marker.SCRATCH_PR.text} {reference(entry)}: run finished, close the"
        " PR and delete its branch"
    ]


def branch_line(entry: Entry, scratch: scratchconfig.Scratch) -> Sequence[str]:
    """The line that flags a PR whose head branch is no run branch.

    Args:
        entry: the PR.
        scratch: the settings.

    Returns:
        The line; none for a run branch, and for a fixture.
    """
    if not entry.off_branch:
        return []
    return [
        f"{Marker.SCRATCH_PR.text} {reference(entry)}: head branch"
        f" {entry.pull.head.branch} is not one of {', '.join(scratch.branches)};"
        " reuse one of them for the next run"
    ]


def _ours(entry: Entry) -> bool:
    return entry.pull.head.repo.lower() == entry.slug.lower()


def _head(entry: Entry) -> tuple[str, str]:
    return entry.pull.head.repo, entry.pull.head.branch


def _delete_line(
    github: ghapi.GitHub, entry: Entry, others: AbstractSet[tuple[str, str]]
) -> str:
    slug, branch = entry.slug, entry.pull.head.branch
    marker = Marker.COULD_NOT_DELETE_SCRATCH_BRANCH.text
    if not _ours(entry):
        where = entry.pull.head.repo or "a repository GitHub does not name"
        return f"{marker} {slug} {branch}: its head is in {where}, not here"
    if _head(entry) in others:
        return f"{marker} {slug} {branch}: another open PR has it as its head"
    try:
        ghapi.delete_branch(github, slug, branch)
    except subprocess.CalledProcessError as error:
        return f"{marker} {slug} {branch}: {ghapi.status_of(error)}"
    return f"{Marker.DELETED_SCRATCH_BRANCH.text} {slug} {branch}"


def _close(github: ghapi.GitHub, entry: Entry) -> tuple[bool, str]:
    try:
        ghapi.close_pull(github, entry.slug, entry.pull.number)
    except subprocess.CalledProcessError as error:
        why = ghapi.status_of(error)
        could = Marker.COULD_NOT_CLOSE_SCRATCH_PR.text
        return False, f"{could} {reference(entry)}: {why}"
    return True, f"{Marker.CLOSED_SCRATCH_PR.text} {reference(entry)}"


def close_finished(github: ghapi.GitHub, look: Look) -> Sequence[str]:
    """Close the PRs whose run finished, then delete their branches.

    A fixture is never touched. A branch that another open PR still has as its
    head, or that lives in another repository, is kept, and said.

    Args:
        github: the API, whose changes really run.
        look: what the scratch repositories hold.

    Returns:
        A line for each PR closed or not, and for each branch.
    """
    closing = [each for each in look.entries if each.finished and not each.kept]
    results = [(each, *_close(github, each)) for each in closing]
    lines = [line for _, _, line in results]
    closed = [each for each, was_closed, _ in results if was_closed]
    done = set(map(reference, closed))
    open_still = [each for each in look.entries if reference(each) not in done]
    others = set(map(_head, filter(_ours, open_still)))
    branches = dict(zip(map(_head, closed), closed))
    deleted = [_delete_line(github, each, others) for each in branches.values()]
    return [*lines, *deleted]


def listing(source: Source) -> Sequence[str]:
    """Flag the scratch PRs that are left behind, and change nothing.

    Args:
        source: what reading needs.

    Returns:
        The lines; none when there is no scratch repository.
    """
    look = read(source)
    lines = list(look.unreadable)
    for each in look.entries:
        lines.extend(finished_line(each))
        lines.extend(branch_line(each, source.scratch))
    return lines


def cleaning(source: Source) -> Sequence[str]:
    """Close the scratch PRs whose run finished and delete their branches.

    A PR from a branch that is no run branch is flagged as well.

    Args:
        source: what reading needs; its API's changes really run.

    Returns:
        The lines; none when there is no scratch repository.
    """
    look = read(source)
    flagged = [
        line for each in look.entries for line in branch_line(each, source.scratch)
    ]
    return [*look.unreadable, *flagged, *close_finished(source.github, look)]
