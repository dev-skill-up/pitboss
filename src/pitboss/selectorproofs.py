"""Every worker task has its typed effects, and the brief is made from them.

pitboss#526 (bats-lang/dom#140). ``workerselect.TABLE`` gives each ``Task`` the
effects its worker may have and must have. P13.3 is the proof over it, read from
the source: one entry for each ``Task``, each with a required effect, no worker
task given but by ``steps.worker``, and the brief's push sentences taken from the
table (``brief`` has no list of its own).
"""

import ast
from typing import AbstractSet, Mapping, Sequence

from .proofcase import Case, Seed
from .enummembers import members
from .proofsource import Package, called, dotted, short

BUILDERS = frozenset({"steps", "finishstep"})


def _facts(node: ast.AST, named: Mapping[str, frozenset[str]]) -> frozenset[str]:
    if isinstance(node, ast.Attribute) and dotted(node.value) == "Effect":
        return frozenset({node.attr})
    if isinstance(node, ast.Name):
        return named.get(node.id, frozenset())
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


def _requiring(
    required: Mapping[str, AbstractSet[str]], outside: AbstractSet[str]
) -> Sequence[str]:
    # the tasks that require nothing, or only what is outside the PR
    empty = [
        f"P13.3: Task.{task} requires no effect"
        for task, got in required.items()
        if not got
    ]
    only = [
        f"P13.3: Task.{task} requires only effects outside the PR"
        for task, got in required.items()
        if got and got <= outside
    ]
    return [*empty, *only]


def required_of(source: ast.AST) -> Mapping[str, AbstractSet[str]]:
    """The effects each task of the table requires, read from its source.

    Args:
        source: the table's module.

    Returns:
        The names of the required effects, by the name of the task.
    """
    named = _constants(source)
    # a task entered twice is read as its last entry: the line that ends the table
    entered = sorted(_entries(source), key=lambda each: each[1].lineno)
    return {task: _facts(call.args[1], named) for task, call in entered}


def required_in(package: Package) -> Mapping[str, AbstractSet[str]]:
    """The effects each task of the package's table requires.

    Args:
        package: the package.

    Returns:
        The names of the required effects, by the name of the task; none when the
        package has no table.
    """
    table = _table(package)
    return required_of(table) if table else {}


def _trees(package: Package) -> Mapping[str, ast.AST]:
    return {short(name): each.syntax for name, each in package.sources.items()}


def _table(package: Package) -> ast.AST | None:
    return _trees(package).get("workerselect")


def entry_findings(source: ast.AST) -> Sequence[str]:
    """What is wrong with the entries of the table.

    Args:
        source: the table's module.

    Returns:
        A line for each task with no entry or two, for each entry that requires
        nothing, and for each that requires only what is outside the PR (a ticket
        filed changes nothing the PR's step is read from).
    """
    named = _constants(source)
    entries = _entries(source)
    given = [task for task, _ in entries]
    found = [
        f"P13.3: Task.{task} has {given.count(task)} entries"
        for task in members(source, "Task")
        if given.count(task) != 1
    ]
    found += _requiring(required_of(source), named.get("OUTSIDE", frozenset()))
    return found


def given_outside(sources: Mapping[str, ast.AST]) -> Sequence[str]:
    """Each call that gives a ``Task`` outside the modules that may.

    Args:
        sources: each module's syntax, by its short name.

    Returns:
        ``module:line`` of each, as a finding.
    """
    return [
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


def brief_findings(sources: Mapping[str, ast.AST]) -> Sequence[str]:
    """What is wrong with where the brief takes its push sentences from.

    Args:
        sources: each module's syntax, by its short name.

    Returns:
        A line when ``brief`` does not read the table, or keeps a list of its own.
    """
    brief = sources.get("brief")
    if brief is None:
        return []
    own = [
        each.id
        for each in ast.walk(brief)
        if isinstance(each, ast.Name) and each.id == "PUSHLESS"
    ]
    reads = [
        each
        for each in ast.walk(brief)
        if isinstance(each, ast.Attribute) and dotted(each) == "workerselect.TABLE"
    ]
    return ["P13.3: brief keeps its own push-less list"] * bool(own) + [
        "P13.3: brief does not read workerselect.TABLE"
    ] * (not reads)


def tasks_can_end_their_selection(package: Package) -> Sequence[str]:
    """P13.3: one entry for each task, each reading a fact its action writes.

    Args:
        package: the package.

    Returns:
        ``entry_findings`` of the table, and each call that gives a ``task`` outside
        ``steps.worker`` (and ``finishstep``, which gives the one that is no PR's
        own fix).
    """
    sources = _trees(package)
    table = sources.get("workerselect")
    if table is None:
        return ["P13.3: the table of worker tasks is missing"]
    found = list(entry_findings(table))
    found += given_outside(sources)
    found += brief_findings(sources)
    return found


CASES: Mapping[str, Case] = {
    "P13.3": Case(
        proof=tasks_can_end_their_selection,
        seed=Seed(
            path="workerselect.py",
            old="_of(Task.REFRESH_BODY, BODY_ONLY, BODY_ONLY)",
            new="_of(Task.REFRESH_BODY, frozenset(), BODY_ONLY)",
        ),
    ),
}
