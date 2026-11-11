"""What ``hand-back-check`` reads of the worker's checkout (keyword: hand-back-done).

(Keyword: hand-back-done, pitboss#471.) A hand-back that names its head (40 hex) is
refused while a job of the worker is still running (a process whose working
directory is in the worktree at that head), a second time for the same head, and
until ``plan-check`` printed ``ok`` at that head and its whole output is posted as
a PR comment whose first line is ``Plan check``. Each refusal says what to do; the
brief carries none of it. Git, ``ps`` and ``gh`` go through the runner, and the
working directory of a process through a reader, so the tests run no real job.
"""

import dataclasses
import hashlib
import json
import os
import pathlib
import re
import subprocess
from typing import Callable, Sequence

from . import ghapi, plantickets
from .running import Run

HEAD = re.compile(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])")
PLAN_CHECK_RECORD = "pitboss-plan-check"
ACCEPTED = "pitboss-hand-backs"
FIRST_LINE = "Plan check"
Cwd = Callable[[int], str]

NO_WORKTREE = (
    "refused: no worktree of the clone is at head {head}; the hand-back names a head"
    " the worker's checkout does not have"
)
RUNNING = "refused: a job you started is still running: {pid} {command}"
AGAIN = (
    "refused: a hand-back for head {head} was already accepted; a worker sends one"
    " hand-back, once, after every command it started has ended"
)
NOT_OK = (
    "refused: `pitboss plan-check` has not printed ok at head {head} in {tree}; run"
    " it there, post its whole output as a PR comment (its first line is"
    " `Plan check`), then hand back"
)
NOT_POSTED = (
    "refused: the output of `pitboss plan-check` at head {head} is not posted as a"
    " PR comment whose first line is `Plan check`; post its whole output, then hand"
    " back"
)


def head_of(text: str) -> str:
    """The head a hand-back names.

    Args:
        text: the hand-back.

    Returns:
        Its first 40-hex word; empty when it has none.
    """
    found = HEAD.search(text)
    return found.group(0) if found else ""


def digest_of(output: str) -> str:
    """The digest of a ``plan-check`` output, as posted.

    Args:
        output: the output.

    Returns:
        The SHA-256 of the output without the whitespace around it.
    """
    return hashlib.sha256(output.strip().encode("utf-8")).hexdigest()


def _lines(path: pathlib.Path) -> Sequence[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return []


def record_plan_check(directory: pathlib.Path, head: str, output: str) -> None:
    """Record that ``plan-check`` printed ``ok`` at a head.

    Args:
        directory: the git directory of the checkout.
        head: the head.
        output: the whole output, which is posted as the comment.
    """
    with (directory / PLAN_CHECK_RECORD).open("a", encoding="utf-8") as stream:
        stream.write(f"{head} {digest_of(output)}\n")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Checkout:
    """The worktree at a head.

    Attributes:
        path: its top-level directory.
        directory: its git directory.
        slug: the repository its ``origin`` names; empty when none.
    """

    path: pathlib.Path
    directory: pathlib.Path
    slug: str


def _out(run: Run, command: Sequence[str]) -> str:
    try:
        return run(command).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return ""


def worktree_at(run: Run, clone: pathlib.Path, head: str) -> Checkout | None:
    """The worktree of a clone whose head is a commit.

    Args:
        run: runs a command line.
        clone: the main clone.
        head: the commit.

    Returns:
        The worktree that is not the clone itself; None when there is none.
    """
    listing = _out(run, ["git", "-C", str(clone), "worktree", "list", "--porcelain"])
    found = None
    for block in listing.split("\n\n"):
        words = dict(each.split(" ", 1) for each in block.splitlines() if " " in each)
        if words.get("HEAD") == head and words.get("worktree") != str(clone):
            found = pathlib.Path(words["worktree"])
            break
    if found is None:
        return None
    where = ["git", "-C", str(found)]
    return Checkout(
        path=found,
        directory=pathlib.Path(_out(run, [*where, "rev-parse", "--absolute-git-dir"])),
        slug=plantickets.slug_of(_out(run, [*where, "remote", "get-url", "origin"])),
    )


def _ancestors(table: dict[int, tuple[int, str]], pid: int) -> set[int]:
    found = {pid}
    while pid in table and table[pid][0] not in found:
        pid = table[pid][0]
        found.add(pid)
    return found


def running_jobs(run: Run, tree: pathlib.Path, own: int, cwd: Cwd) -> Sequence[str]:
    """The processes that work in a worktree, but this command and its parents.

    Args:
        run: runs a command line.
        tree: the worktree.
        own: the process id of this command.
        cwd: reads a process's working directory (empty when it cannot).

    Returns:
        ``pid command`` of each, in the order ``ps`` lists them.
    """
    listing = _out(run, ["ps", "-eo", "pid=,ppid=,args="]).splitlines()
    table = {}
    for each in listing:
        words = each.split(None, 2)
        if len(words) == 3 and words[0].isdigit() and words[1].isdigit():
            table[int(words[0])] = (int(words[1]), words[2])
    skipped = _ancestors(table, own)
    inside = [
        pid
        for pid in table
        if pid not in skipped
        and cwd(pid) != ""
        and pathlib.Path(cwd(pid)).is_relative_to(tree)
    ]
    return [f"{pid} {table[pid][1]}" for pid in inside]


def proc_cwd(pid: int) -> str:
    """The working directory of a process, where the system says it.

    Args:
        pid: the process.

    Returns:
        The directory; empty when the system does not say.
    """
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return ""


def _posted(github: ghapi.GitHub, checkout: Checkout, head: str, seen: str) -> bool:
    if not checkout.slug:
        return False
    try:
        pulls = json.loads(
            ghapi.get(github, f"repos/{checkout.slug}/commits/{head}/pulls")
        )
        for each in pulls:
            path = f"repos/{checkout.slug}/issues/{each['number']}/comments"
            comments = ghapi.pages(github, path, json.loads)
            if any(_is_check(one, seen) for one in comments):
                return True
    except (subprocess.CalledProcessError, ValueError, KeyError, TypeError):
        return False
    return False


def _is_check(comment: dict[str, str], seen: str) -> bool:
    body = str(comment.get("body", "")).replace("\r\n", "\n")
    first = body.splitlines()[0].rstrip() if body.strip() else ""
    return first == FIRST_LINE and digest_of(body) == seen


def plan_check_findings(
    github: ghapi.GitHub, checkout: Checkout, head: str
) -> Sequence[str]:
    """The refusals about the Plan check of a head.

    Args:
        github: the API.
        checkout: the worktree at the head.
        head: the head.

    Returns:
        A line when ``plan-check`` printed no ``ok`` at the head, or its output
        is not posted; none otherwise.
    """
    seen = [
        each.split(" ", 1)[1]
        for each in _lines(checkout.directory / PLAN_CHECK_RECORD)
        if each.startswith(f"{head} ")
    ]
    if not seen:
        return [NOT_OK.format(head=head, tree=checkout.path)]
    if not any(_posted(github, checkout, head, each) for each in seen):
        return [NOT_POSTED.format(head=head)]
    return []


def accepted_path(run: Run, clone: pathlib.Path) -> pathlib.Path:
    """The file that records the heads whose hand-back was accepted.

    Args:
        run: runs a command line.
        clone: the main clone.

    Returns:
        The file in the clone's git directory.
    """
    base = _out(
        run,
        [
            "git",
            "-C",
            str(clone),
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
        ],
    )
    return pathlib.Path(base) / ACCEPTED


def findings(run: Run, clone: pathlib.Path, head: str, cwd: Cwd) -> Sequence[str]:
    """Every refusal about the checkout a hand-back names.

    Args:
        run: runs a command line (``gh`` too).
        clone: the main clone.
        head: the head the hand-back names.
        cwd: reads a process's working directory.

    Returns:
        The refusal lines; none when the hand-back may be accepted.
    """
    if head in _lines(accepted_path(run, clone)):
        return [AGAIN.format(head=head)]
    checkout = worktree_at(run, clone, head)
    if checkout is None:
        return [NO_WORKTREE.format(head=head)]
    jobs = running_jobs(run, checkout.path, os.getpid(), cwd)
    return [
        *(
            RUNNING.format(pid=each.split(" ", 1)[0], command=each.split(" ", 1)[1])
            for each in jobs
        ),
        *plan_check_findings(ghapi.read_only(run), checkout, head),
    ]


def accept(run: Run, clone: pathlib.Path, head: str) -> None:
    """Record that the hand-back of a head was accepted.

    Args:
        run: runs a command line.
        clone: the main clone.
        head: the head.
    """
    with accepted_path(run, clone).open("a", encoding="utf-8") as stream:
        stream.write(f"{head}\n")
