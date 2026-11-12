"""What stands between a worker and its one hand-back (keyword: hand-back-done).

A hand-back is the end of a worker: it is sent once, for a PR head, after every
job the worker started has ended, and after the Plan check of the pushed head is
posted (pitboss#471). ``hand-back-check`` refuses otherwise, and says what to do
in the refusal, so the brief has no line for any of it.
"""

import dataclasses
import json
import os
import pathlib
import subprocess
from typing import AbstractSet, Protocol, Sequence

from . import (
    evidence,
    forms,
    ghapi,
    parsing,
    plancheckflow,
    pullfiles,
    relockfix,
    shapes,
)

SHOWN = 100


def _ancestors(proc: pathlib.Path, pid: int) -> frozenset[int]:
    # the process and its parents: the shell that runs the check is the worker's own
    found = {pid}
    while pid > 1:
        try:
            stat = (proc / str(pid) / "stat").read_text(encoding="utf-8")
            pid = int(stat.rpartition(")")[2].split()[1])
        except (OSError, ValueError, IndexError):
            break
        if pid in found:  # pragma: no cover
            break
        found.add(pid)
    return frozenset(found)


def _inside(cwd: str, root: pathlib.Path) -> bool:
    return cwd == str(root) or cwd.startswith(str(root) + os.sep)


def _command(proc: pathlib.Path, entry: str) -> str:
    try:
        raw = (proc / entry / "cmdline").read_bytes()
    except OSError:
        return "(unreadable)"
    words = raw.decode("utf-8", errors="replace").replace("\0", " ").strip()
    return (words or "(no command line)")[:SHOWN]


def running_jobs(root: pathlib.Path, proc: pathlib.Path, own: int) -> Sequence[str]:
    """The processes that run in a worktree and are not the check itself.

    Args:
        root: the worktree.
        proc: the directory of process entries (``/proc``).
        own: the process id of the check; it and its parents are not jobs.

    Returns:
        ``<pid> <command line>`` for each other process whose working directory
        is the worktree or below it.
    """
    skip = _ancestors(proc, own)
    found = []
    for entry in sorted(each.name for each in proc.iterdir() if each.name.isdigit()):
        try:
            cwd = os.readlink(proc / entry / "cwd")
        except OSError:
            continue
        if int(entry) not in skip and _inside(cwd, root):
            found.append(f"{entry} {_command(proc, entry)}")
    return found


def jobs_line(found: Sequence[str]) -> str:
    """The refusal for jobs the worker started that still run.

    Args:
        found: ``running_jobs``.

    Returns:
        The line, empty when none runs.
    """
    if not found:
        return ""
    return (
        f"refused: a job you started is still running: {found[0]}"
        + (f" (and {len(found) - 1} more)" if len(found) > 1 else "")
        + "; wait for it in the foreground (a command's own timeout) and send"
        " the hand-back once, after every command has ended"
    )


def second_line(head: str) -> str:
    """The refusal of a second hand-back for a head.

    Args:
        head: the head.

    Returns:
        The line.
    """
    return (
        f"refused: the hand-back for head {head} was already accepted; it is sent"
        " once, and a second one is not a report"
    )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Pushed:
    """The PR a hand-back is for.

    Attributes:
        github: the API.
        slug: the repository's ``owner/name``.
        number: the PR.
        head: the worktree's head, the one that was pushed.
        trusted: the author associations whose comments count.
        branch: the branch the worktree is on, the one the worker pushed to; empty
            when it is not told (keyword: claim-readback, quire#1115).
    """

    github: ghapi.GitHub
    slug: str
    number: int
    head: str
    trusted: AbstractSet[str]
    branch: str = ""

    @property
    def name(self) -> str:
        """The PR as ``owner/name#number``.

        Returns:
            The text.
        """
        return f"{self.slug}#{self.number}"


class Subject(Protocol):
    """The PR a hand-back is for (``Pushed``)."""

    @property
    def github(self) -> ghapi.GitHub:
        """The API.

        Returns:
            The value.
        """

    @property
    def slug(self) -> str:
        """The repository's ``owner/name``.

        Returns:
            The value.
        """

    @property
    def number(self) -> int:
        """The PR.

        Returns:
            The value.
        """

    @property
    def head(self) -> str:
        """The pushed head.

        Returns:
            The value.
        """

    @property
    def trusted(self) -> AbstractSet[str]:
        """The author associations whose comments count.

        Returns:
            The value.
        """

    @property
    def name(self) -> str:
        """The PR as ``owner/name#number``.

        Returns:
            The value.
        """

    @property
    def branch(self) -> str:
        """The branch pushed to.

        Returns:
            The value.
        """


def branch_pull(github: ghapi.GitHub, slug: str, branch: str) -> int | str:
    """The open PR whose head branch is a worktree's branch.

    Args:
        github: the API.
        slug: the repository's ``owner/name``.
        branch: the worktree's branch.

    Returns:
        The PR number, or the refusal line when no open PR holds the branch or
        the list cannot be read.
    """
    path = f"repos/{slug}/pulls?state=open&head={slug.partition('/')[0]}:{branch}"
    try:
        listed = json.loads(ghapi.get(github, path))
    except subprocess.CalledProcessError as error:
        why = ghapi.why(error)
        return f"refused: the open PRs of branch {branch} cannot be read: {why}"
    if not listed:
        return (
            f"refused: no open PR of {slug} holds the branch {branch}: open the PR"
            " first, or give it with --pr"
        )
    return int(listed[0]["number"])


def _head_lines(pushed: Subject, pull: shapes.Pull) -> Sequence[str]:
    named = forms.HEAD_LINE.findall(pull.body)
    found = []
    if pushed.branch and pull.head.branch != pushed.branch:
        found.append(  # keyword: claim-readback (quire#1115)
            f"refused: WRONG-BRANCH {pushed.name}: the PR's head branch is"
            f" {pull.head.branch} (at {pull.head.sha}), but you pushed"
            f" {pushed.branch}: push to {pull.head.branch}"
        )
    if pull.head.sha != pushed.head:
        found.append(
            f"refused: {pushed.name} holds head {pull.head.sha}, not the pushed"
            f" head {pushed.head}: push first"
        )
    if not named or named[-1] != pushed.head:
        found.append(
            f"refused: the body of {pushed.name} has no last `Head:` line"
            f" naming {pushed.head}: edit the body"
        )
    found.extend(  # case 27 (keyword: evidence-head): the blocks name the head
        f"refused: {pushed.name}: {each}: re-run `uvx pitboss expand`"
        for each in evidence.stale_heads(pull.body, named[-1] if named else "")
    )
    return found


def pull_lines(pushed: Subject) -> Sequence[str]:
    """The refusals of a PR whose Plan check is not posted at the pushed head.

    Args:
        pushed: the PR and the head.

    Returns:
        A line for each thing missing; none when the PR holds the head, its body
        names the head and a clean ``Plan check`` of its Plan is posted.
    """
    base = f"repos/{pushed.slug}"
    pull = parsing.pull(ghapi.get(pushed.github, f"{base}/pulls/{pushed.number}"))
    where = f"{base}/issues/{pushed.number}/comments"
    listed = ghapi.pages(pushed.github, where, parsing.comments)
    found = list(_head_lines(pushed, pull))
    if plancheckflow.needs_check(pull.body, listed, pushed.trusted):
        found.append(
            "refused: the hand-back is not done until the Plan check of this"
            " head is posted: run `uvx pitboss plan-check BODYFILE --repo"
            f" WORKTREE --head {pushed.head} --config CONFIG` and post its whole"
            " output as a PR comment (first line `Plan check`, last `Plan check:"
            " ok`); a refusal is fixed by you, not by a new round"
        )
    return [*found, *_relock_lines(pushed, pull, listed)]


def _relock_lines(
    pushed: Subject, pull: shapes.Pull, listed: Sequence[shapes.Comment]
) -> Sequence[str]:
    # keyword: relock-test-fix (pitboss#447): the data behind a test change
    if not pull.head.branch.startswith(relockfix.RELOCK_PREFIX):
        return []
    path = f"repos/{pushed.slug}/pulls/{pushed.number}/files"
    names = ghapi.pages(pushed.github, path, pullfiles.file_names)
    said = [each.body for each in listed if each.body.lstrip().startswith("Test fix")]
    return relockfix.findings(pull.body, said[-1] if said else "", names)
