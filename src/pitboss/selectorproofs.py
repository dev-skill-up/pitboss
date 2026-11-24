"""A selected worker task can end its own selection (keyword: worker-select).

pitboss#526 (bats-lang/dom#140): a task selected by a fact its action cannot change
is selected for ever. ``workerselect.TABLE`` pairs each ``Task`` with the facts it is
selected by and those its action changes; this is the proof over it, read from the
source: P13.3 has one entry for each ``Task``, every entry reads a fact its action
writes, an entry that reads text names the fact that ends it, and no worker step is
built but by ``workerselect.worker``.
"""

import ast
from typing import Mapping, Sequence

from .proofcase import Case, Seed
from .proofsource import Package, called, dotted, short


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
def _entries(source: ast.Module) -> list[tuple[str, ast.Call]]:
    return [
        (node.args[0].attr, node)
        for node in ast.walk(source)
        if called(node) == "_of"
        and isinstance(node, ast.Call)
        and isinstance(node.args[0], ast.Attribute)
    ]


# the members of ``steps.Task``
def _tasks(source: ast.Module) -> list[str]:
    return [
        target.id
        for node in ast.walk(source)
        if isinstance(node, ast.ClassDef) and node.name == "Task"
        for each in node.body
        if isinstance(each, ast.Assign)
        for target in each.targets
        if isinstance(target, ast.Name)
    ]


# the module's named fact sets (``PUSH``, ``EDIT``)
def _constants(source: ast.Module) -> dict[str, frozenset[str]]:
    found: dict[str, frozenset[str]] = {}
    for node in source.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            found[node.targets[0].id] = _facts(node.value, found)
    return found


def entry_findings(source: ast.Module, steps_source: ast.Module) -> Sequence[str]:
    """What is wrong with the entries of the table.

    Args:
        source: the table's module.
        steps_source: the module of ``Task``.

    Returns:
        A line for each task with no entry or two, each entry that reads no fact its
        action writes and each that reads text with no fact that ends it.
    """
    named = _constants(source)
    entries = _entries(source)
    given = [task for task, _ in entries]
    found = [
        f"P13.3: Task.{task} has {given.count(task)} entries"
        for task in _tasks(steps_source)
        if given.count(task) != 1
    ]
    for task, call in entries:
        reads, writes = (_facts(call.args[index], named) for index in (1, 2))
        ends = _facts(call.args[3], named) if len(call.args) > 3 else frozenset()
        if not (reads - {"TEXT"}) & writes:
            found.append(f"P13.3: Task.{task} reads no fact its action writes")
        if "TEXT" in reads and not ends & writes:
            found.append(f"P13.3: Task.{task} reads text and nothing ends it")
    return found


def tasks_can_end_their_selection(package: Package) -> Sequence[str]:
    """P13.3: one entry for each task, each reading a fact its action writes.

    Args:
        package: the package.

    Returns:
        ``entry_findings`` of the table, and each call of ``steps.worker`` outside
        the table's module.
    """
    sources = {short(name): each.syntax for name, each in package.sources.items()}
    found = list(entry_findings(sources["workerselect"], sources["steps"]))
    found += [
        f"P13.3: {name}:{node.lineno} builds a worker step outside the table"
        for name, tree in sources.items()
        if name != "workerselect"
        for node in ast.walk(tree)
        if called(node) == "steps.worker" and isinstance(node, ast.Call)
    ]
    return found


CASES: Mapping[str, Case] = {
    "P13.3": Case(
        proof=tasks_can_end_their_selection,
        seed=Seed(
            path="workerselect.py",
            old="_of(steps.Task.FIX_CI, {Fact.CHECKS}, PUSH)",
            new="_of(steps.Task.FIX_CI, {Fact.CHECKS}, EDIT - {Fact.REVIEWS})",
        ),
    ),
}
