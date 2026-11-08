"""Which tests a change can affect (keyword: test-selection, pitboss#331).

``pitboss nox`` runs the tests chosen here and says why. A test is selected when
a changed module is one of the modules it imports, directly or through other
modules, or is the test itself (the graph and the two links no import states are
``importgraph``'s). What the graph cannot place runs everything
(``affected_by``): a changed file that is not a module of the package (a skill, a
doc, a config, ``noxfile.py``, a data file), a changed or deleted shared module
of the tests, a deleted module, and a package that has a file ``ast`` cannot
parse. The reasons and the unsafe cases are in the pull request that made this
(pitboss#331).
"""

import dataclasses
from collections.abc import Mapping, Sequence

from . import importgraph

SHOWN_PATHS = 3
NONE_REACHED = "test-selection no test is reached by the change, so no test runs"
NOT_CHECKED = (
    "test-selection coverage of the left-out tests is not checked here; CI's"
    " `Run Nox` step checks the whole suite at 100%"
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Change:
    """A file the diff changed.

    Attributes:
        path: its path from the root of the repository.
        deleted: whether it is gone at the head.
    """

    path: str
    deleted: bool


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Selection:
    """The tests a diff can affect.

    Attributes:
        everything: why the whole suite runs; empty when the choice was made.
        chosen: for each selected test module, the changed files that reach it.
        total: how many test modules there are.
    """

    everything: str
    chosen: Mapping[str, Sequence[str]]
    total: int


def everything(graph: importgraph.Graph, why: str) -> Selection:
    """The whole suite.

    Args:
        graph: the graph.
        why: the reason.

    Returns:
        A selection that runs every test.
    """
    return Selection(everything=why, chosen={}, total=len(importgraph.tests_of(graph)))


def unplaced(change: Change) -> str:
    """Why a changed file cannot be placed on the graph.

    Args:
        change: the changed file.

    Returns:
        The reason; empty when the file is a module of the package or a test
        (a deleted test is no module, but its tests are gone with it).
    """
    module = importgraph.module_of(change.path)
    if not module:
        return f"{change.path} is outside the map"
    if importgraph.is_test(module):
        return ""
    if importgraph.in_tests(module):
        return f"{change.path} is a shared module of the tests"
    return f"{change.path} is deleted" if change.deleted else ""


def affected_by(graph: importgraph.Graph, changes: Sequence[Change]) -> Selection:
    """Choose the tests a diff can affect, or the whole suite.

    Args:
        graph: the graph of the head.
        changes: the files the diff changed.

    Returns:
        The tests to run, each with the changed files that reach it; the whole
        suite (``everything`` says why) when a changed file cannot be placed.
    """
    reasons = [unplaced(each) for each in changes]
    if graph.unreadable:
        return everything(graph, f"{sorted(graph.unreadable)[0]} cannot be parsed")
    if any(reasons):
        return everything(graph, next(each for each in reasons if each))
    chosen: dict[str, list[str]] = {}
    wanted = importgraph.tests_of(graph)
    for each in (found for found in changes if not found.deleted):
        reached = importgraph.dependents(graph, importgraph.module_of(each.path))
        for test in wanted:
            if test in reached:
                chosen.setdefault(test, []).append(each.path)
    return Selection(everything="", chosen=chosen, total=len(wanted))


def lines_of(selection: Selection) -> Sequence[str]:
    """What ``pitboss nox`` prints about a selection.

    Args:
        selection: the selection.

    Returns:
        The lines, each starting with ``test-selection``.
    """
    if selection.everything:
        return [f"test-selection all test modules: {selection.everything}"]
    lines = []
    for test, paths in sorted(selection.chosen.items()):
        shown = ", ".join(paths[:SHOWN_PATHS])
        more = len(paths) - SHOWN_PATHS
        tail = f" and {more} more" if more > 0 else ""
        lines.append(f"test-selection {test}: {shown}{tail}")
    chosen = len(selection.chosen)
    if not chosen:
        lines.append(NONE_REACHED)
    lines.append(
        f"test-selection selected {chosen} of {selection.total} test modules,"
        f" left out {selection.total - chosen}"
    )
    lines.append(NOT_CHECKED)
    return lines
