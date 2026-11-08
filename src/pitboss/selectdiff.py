"""The diff ``pitboss nox`` selects tests from (keyword: test-selection, pitboss#331).

The diff is the working tree against the merge base of ``origin/main`` and
``HEAD``, so a commit, an uncommitted edit and a new file all count. A git
command that fails means the diff cannot be known, and then the whole suite runs
(``testselect.select`` says what is run when a file cannot be placed).
"""

import dataclasses
import pathlib
from collections.abc import Mapping, Sequence

from . import importgraph, testselect
from .noxcheck import Runner

BASE = "origin/main"
SHORT_SHA = 7
LIST_NEW = ["git", "ls-files", "--others", "--exclude-standard", "-z", "--full-name"]
NO_BASE = f"git could not say the root or the merge base with {BASE}"
NO_LIST = "git could not list the files that differ"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Diff:
    """What git said about the change.

    Attributes:
        root: the root of the repository.
        base: the merge base.
        changes: the files that differ from the merge base.
        problem: why the diff is not known; empty when it is.
    """

    root: str
    base: str
    changes: Sequence[testselect.Change]
    problem: str


def words_of(text: str) -> Sequence[str]:
    """The pieces of a ``-z`` listing.

    Args:
        text: git's output.

    Returns:
        Each piece that is not empty.
    """
    return [each for each in text.split("\0") if each]


def changes_of(listing: str, others: str) -> Sequence[testselect.Change]:
    """The changed files, from ``git diff --name-status -z`` and the new files.

    Args:
        listing: the output of ``git diff --name-status --no-renames -z``: a
            status and a path, one after the other.
        others: the output of ``git ls-files --others -z``: untracked paths.

    Returns:
        A change for each path, a deleted one marked.
    """
    pieces = words_of(listing)
    found = {
        path: testselect.Change(path=path, deleted=status == "D")
        for status, path in zip(pieces[::2], pieces[1::2])
    }
    new = {
        each: testselect.Change(path=each, deleted=False) for each in words_of(others)
    }
    return list({**new, **found}.values())


def diff_of(run: Runner) -> Diff:
    """Ask git for the diff against the merge base.

    Args:
        run: runs a command line.

    Returns:
        The diff; with ``problem`` set when a git command failed.
    """
    root = run(["git", "rev-parse", "--show-toplevel"])
    base = run(["git", "merge-base", BASE, "HEAD"])
    if root.status or base.status:
        return Diff(root="", base="", changes=[], problem=NO_BASE)
    point = base.output.strip()
    listing = run(["git", "diff", "--name-status", "--no-renames", "-z", point])
    others = run(LIST_NEW)
    if listing.status or others.status:
        return Diff(root="", base=point, changes=[], problem=NO_LIST)
    return Diff(
        root=root.output.strip(),
        base=point,
        changes=changes_of(listing.output, others.output),
        problem="",
    )


def sources_of(root: str) -> Mapping[str, str]:
    """The text of each ``.py`` file of the package at the head.

    Args:
        root: the root of the repository.

    Returns:
        The text by path from the root.
    """
    top = pathlib.Path(root)
    return {
        each.relative_to(top).as_posix(): each.read_text(encoding="utf-8")
        for each in sorted((top / importgraph.SOURCE).rglob("*.py"))
    }


def choose(run: Runner) -> tuple[Sequence[str], testselect.Selection]:
    """Select the tests the change can affect.

    Args:
        run: runs a command line.

    Returns:
        The lines to print, and the selection.
    """
    diff = diff_of(run)
    if diff.problem:
        gone = testselect.Selection(
            everything=diff.problem, chosen={}, total=0, changed=[]
        )
        return testselect.lines_of(gone), gone
    graph = importgraph.build_graph(sources_of(diff.root))
    found = testselect.affected_by(graph, diff.changes)
    head = (
        f"test-selection diff against the merge base {diff.base[:SHORT_SHA]}"
        f" with {BASE}, files that differ: {len(diff.changes)}"
    )
    return [head, *testselect.lines_of(found)], found
