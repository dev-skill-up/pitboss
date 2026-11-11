"""What stands between a worker and its one hand-back (keyword: hand-back-done).

A hand-back is the end of a worker: it is sent once, for a PR head, after every
job the worker started has ended, and after the Plan check of the pushed head is
posted (pitboss#471). ``hand-back-check`` refuses otherwise, and says what to do
in the refusal, so the brief has no line for any of it.
"""

import dataclasses
import os
import pathlib
from typing import AbstractSet, Protocol, Sequence

from . import forms, ghapi, parsing, plancheckflow, shapes

RECORD = "pitboss-hand-back"
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


def recorded(git_directory: pathlib.Path, head: str) -> bool:
    """Whether a hand-back was already accepted for a head.

    Args:
        git_directory: the worktree's git directory.
        head: the head the hand-back is for.

    Returns:
        True when the record names it.
    """
    try:
        text = (git_directory / RECORD).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    return head in text.split()


def record(git_directory: pathlib.Path, head: str) -> None:
    """Record that a hand-back was accepted for a head.

    Args:
        git_directory: the worktree's git directory.
        head: the head.
    """
    try:
        with (git_directory / RECORD).open("a", encoding="utf-8") as kept:
            kept.write(f"{head}\n")
    except OSError:  # pragma: no cover
        return


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
    """

    github: ghapi.GitHub
    slug: str
    number: int
    head: str
    trusted: AbstractSet[str]

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


def _head_lines(pushed: Subject, pull: shapes.Pull) -> Sequence[str]:
    named = forms.HEAD_LINE.findall(pull.body)
    found = []
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
    return found
