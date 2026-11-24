"""A selected worker task can end its own selection (keyword: worker-select).

pitboss#526 (bats-lang/dom#140): a task selected by a fact its action cannot change
is selected for ever. ``workerselect.TABLE`` pairs each ``Task`` with the facts it is
selected by and those its action changes. P13.3 is the proof over it, read from the
source. It wants one entry for each ``Task``, every entry reading a fact its action
writes, an entry that reads text naming the fact that ends it, and no worker task
given but by ``steps.worker``.
"""

import ast
from typing import AbstractSet, Mapping, Sequence

from .proofcase import Case, Seed
from .enummembers import members
from .proofsource import Package, called, dotted, short

BUILDERS = frozenset({"steps", "finishstep"})


def _facts(node: ast.AST, named: Mapping[str, frozenset[str]]) -> frozenset[str]:

    if isinstance(node, ast.Attribute) and dotted(node.value) == "Fact":
        return frozenset({node.attr})
    if isinstance(node, ast.Name):
        return named.get(node.id, frozenset())
    if isinstance(node, ast.BinOp):
        return _facts(node.left, named) | _facts(node.right, named)
    return frozenset().union(
        *(_facts(each, named) for each in ast.iter_child_nodes(node))
    )


# the ``_of(steps.Task.X, ...)`` calls of the table, with the task named
def _entries(source: ast.AST) -> list[tuple[str, ast.Call]]:
    return [
        (node.args[0].attr, node)
        for node in ast.walk(source)
        if called(node) == "_of"
        and isinstance(node, ast.Call)
        and isinstance(node.args[0], ast.Attribute)
    ]


# the module's named fact sets (``PUSH``, ``EDIT``)
def _constants(source: ast.AST) -> dict[str, frozenset[str]]:
    found: dict[str, frozenset[str]] = {}
    for node in ast.iter_child_nodes(source):
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            found[node.targets[0].id] = _facts(node.value, found)
    return found


# what one entry says wrong: reads nothing it writes, or a text and no end of it
def _problems(
    task: str, reads: AbstractSet[str], writes: AbstractSet[str], ends: AbstractSet[str]
) -> Sequence[str]:
    return [
        f"P13.3: Task.{task} {why}"
        for why, bad in (
            ("reads no fact its action writes", not reads - {"TEXT"} & writes),
            ("reads text and nothing ends it", "TEXT" in reads and not ends & writes),
        )
        if bad
    ]


def entry_findings(source: ast.AST) -> Sequence[str]:
    """What is wrong with the entries of the table.

    Args:
        source: the table's module.

    Returns:
        A line for each task with no entry or two, each entry that reads no fact its
        action writes and each that reads text with no fact that ends it.
    """
    named = _constants(source)
    entries = _entries(source)
    given = [task for task, _ in entries]
    found = [
        f"P13.3: Task.{task} has {given.count(task)} entries"
        for task in members(source, "Task")
        if given.count(task) != 1
    ]
    for task, call in entries:
        reads, writes = (_facts(call.args[index], named) for index in (1, 2))
        ends = _facts(call.args[3], named) if len(call.args) > 3 else frozenset()
        found += _problems(task, reads, writes, ends)
    return found


def tasks_can_end_their_selection(package: Package) -> Sequence[str]:
    """P13.3: one entry for each task, each reading a fact its action writes.

    Args:
        package: the package.

    Returns:
        ``entry_findings`` of the table, and each call that gives a ``task`` outside
        ``steps.worker`` (and ``finishstep``, which gives the one that is no PR's
        own fix).
    """
    sources = {short(name): each.syntax for name, each in package.sources.items()}
    found = list(entry_findings(sources["workerselect"]))
    found += [
        f"P13.3: {name}:{node.lineno} gives a worker task outside steps.worker"
        for name, tree in sources.items()
        if name not in BUILDERS
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and any(
            each.arg == "task" and ".Task." in f".{dotted(each.value)}"
            for each in node.keywords
        )
    ]
    return found


CASES: Mapping[str, Case] = {
    "P13.3": Case(
        proof=tasks_can_end_their_selection,
        seed=Seed(
            path="workerselect.py",
            old="_of(Task.FIX_CI, {Fact.CHECKS}, PUSH)",
            new="_of(Task.FIX_CI, {Fact.CHECKS}, EDIT - {Fact.REVIEWS})",
        ),
    ),
}
