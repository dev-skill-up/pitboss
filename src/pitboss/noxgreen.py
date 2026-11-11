"""A head already green is not run again (keyword: nox-green, pitboss#345).

The owner's rule: ``pitboss nox`` runs before each push and when feedback is
needed, not again on a head it already passed. A passing run on a clean tree
writes ``pitboss-nox-green`` in the repository's git directory, with the head and
the time; a later run on the same clean head prints ``NOTE`` and exits 0 without
running unless ``--force`` is given. A dirty tree is never recorded or skipped:
it is not a head. Git and the clock are injected, so the tests run no real git.
"""

import dataclasses
import pathlib
from typing import AbstractSet, Sequence

from .noxcheck import Runner

RECORD = "pitboss-nox-green"
HEAD = ["git", "rev-parse", "HEAD"]
DIRECTORY = ["git", "rev-parse", "--absolute-git-dir"]
STATUS = ["git", "status", "--porcelain"]
TREE = ["git", "rev-parse", "HEAD^{tree}"]
TREE_RECORD = "pitboss-nox-trees"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Place:
    """Where a clean head's green run is recorded.

    Attributes:
        head: the head commit.
        path: the file that records the green run.
        tree: the tree of the head, which ``pitboss push`` asks for (keyword:
            nox-tree, pitboss#471).
    """

    head: str
    path: pathlib.Path
    tree: str = ""


def note_of(when: str) -> str:
    """The line printed for a head that already ran green.

    Args:
        when: the time of the green run.

    Returns:
        The line.
    """
    return (
        f"NOTE: this head already ran green at {when}; rerun only when feedback"
        " is needed (--force runs it again)"
    )


def place_of(run: Runner) -> Place | None:
    """The record of the clean head of the repository the command runs in.

    Args:
        run: runs a command line (git).

    Returns:
        The head and its record file; none when git cannot say, or when the
        tree has a change (a head is only a clean tree).
    """
    head, directory, status = run(HEAD), run(DIRECTORY), run(STATUS)
    tree = run(TREE)
    if head.status or directory.status or status.status or status.output.strip():
        return None
    return Place(
        head=head.output.strip(),
        path=pathlib.Path(directory.output.strip()) / RECORD,
        tree="" if tree.status else tree.output.strip(),
    )


def green_at(place: Place) -> str:
    """The time a head ran green.

    Args:
        place: the head and its record file.

    Returns:
        The time recorded for the head; empty when the record is missing,
        unreadable or for another head.
    """
    try:
        head, _, when = place.path.read_text(encoding="utf-8").strip().partition(" ")
    except (OSError, UnicodeError):
        return ""
    return when if head == place.head else ""


def record(place: Place, when: str, sessions: Sequence[str] = ()) -> None:
    """Record that a head ran green, and its tree with the sessions that ran.

    Args:
        place: the head and its record file.
        when: the time.
        sessions: the names of the sessions that ran and passed.
    """
    try:
        place.path.write_text(f"{place.head} {when}\n", encoding="utf-8")
        if place.tree:  # pragma: no branch
            line = f"{place.tree} {when} {','.join(sessions)}\n"
            with (place.path.with_name(TREE_RECORD)).open(
                "a", encoding="utf-8"
            ) as kept:
                kept.write(line)
    except OSError:  # pragma: no cover
        return


def ran_green(git_directory: pathlib.Path, tree: str) -> AbstractSet[str]:
    """The sessions that ran green on a tree (keyword: nox-tree, pitboss#471).

    Args:
        git_directory: the git directory of the repository.
        tree: the tree hash.

    Returns:
        The names of the sessions a green ``pitboss nox`` ran on that exact tree;
        none when nothing is recorded for it.
    """
    try:
        text = (git_directory / TREE_RECORD).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return frozenset()
    found: set[str] = set()
    for each in text.splitlines():
        words = each.split()
        if words[:1] == [tree] and len(words) > 2:
            found.update(words[2].split(","))
    return found


def missing_line(tree: str, absent: Sequence[str]) -> str:
    """The line ``pitboss push`` prints for a tree with no green nox.

    Args:
        tree: the tree hash.
        absent: the sessions with no green result for it.

    Returns:
        The line.
    """
    return (
        f"push REFUSED: no green `pitboss nox` is recorded for tree {tree}; missing"
        f" sessions: {', '.join(absent)}; run `pitboss nox` on this tree (CI is not"
        " the check) and push again"
    )
