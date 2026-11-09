"""What the scans of the tests share: files, findings and names (pitboss#402).

The two rules (keyword: captured-run) read the syntax of the files of the
tests. ``capturescan`` reads for a command whose output is kept, ``poolscan``
for a subprocess run from a pool or a thread.
"""

import ast
import dataclasses
import pathlib
import subprocess
from collections.abc import Mapping, Sequence, Set

SUBPROCESS = "subprocess"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Finding:
    """A place in a file of the tests that a rule refuses.

    Attributes:
        path: the file.
        line: the line of the call.
        name: the function that holds the call, or the one a pool runs.
        why: what is wrong.
    """

    path: str
    line: int
    name: str
    why: str


def shown(finding: Finding) -> str:
    """A finding as a line.

    Args:
        finding: the finding.

    Returns:
        The path, the line, the name and the reason.
    """
    return f"{finding.path}:{finding.line}: {finding.name}: {finding.why}"


def sources(directory: pathlib.Path) -> Mapping[str, str]:
    """The text of every Python file under a directory.

    Args:
        directory: the directory of the tests.

    Returns:
        The text of each, by its name under the directory.
    """
    return {
        str(each.relative_to(directory)): each.read_text(encoding="utf-8")
        for each in sorted(directory.rglob("*.py"))
    }


def named(node: ast.AST) -> str:
    """The last name of what a call calls.

    Args:
        node: the function of a call.

    Returns:
        ``run`` for ``subprocess.run`` and for ``run``; empty for anything else.
    """
    if isinstance(node, ast.Attribute):
        return node.attr
    return node.id if isinstance(node, ast.Name) else ""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Bindings:
    """What a file's imports bind to the ``subprocess`` module (keyword: captured-run).

    Attributes:
        modules: the names the module is bound to (``subprocess``, ``sp``).
        functions: the names its functions are bound to, by the function's own name.
    """

    modules: Set[str]
    functions: Mapping[str, str]


def defs(tree: ast.AST) -> Sequence[ast.FunctionDef | ast.AsyncFunctionDef]:
    """The ``def`` and ``async def`` of a file, wherever they are.

    Args:
        tree: the parsed file.

    Returns:
        Them.
    """
    return [
        x
        for x in ast.walk(tree)
        if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def imported_functions(node: ast.AST) -> Mapping[str, str]:
    """The names a ``from subprocess import`` statement binds, by the function's name.

    Args:
        node: any node.

    Returns:
        The local name of each function; ``*`` binds them all; none for any
        other node.
    """
    if not (
        isinstance(node, ast.ImportFrom)
        and node.module == SUBPROCESS
        and not node.level
    ):
        return {}
    if any(each.name == "*" for each in node.names):
        return {x: x for x in subprocess.__all__}
    return {(each.asname or each.name): each.name for each in node.names}


def imported_modules(node: ast.AST) -> Set[str]:
    """The names an ``import subprocess`` statement binds.

    Args:
        node: any node.

    Returns:
        The local names of the module; none for any other node.
    """
    names = node.names if isinstance(node, ast.Import) else []
    return {each.asname or each.name for each in names if each.name == SUBPROCESS}


def bound_by(tree: ast.AST) -> Bindings:
    """The names a file binds to ``subprocess`` and to its functions.

    Args:
        tree: the parsed file.

    Returns:
        The names of ``import subprocess [as x]``, and of
        ``from subprocess import f [as g]`` and ``from subprocess import *``,
        wherever in the file they are.
    """
    nodes = list(ast.walk(tree))
    return Bindings(
        modules={name for each in nodes for name in imported_modules(each)},
        functions={
            name: own
            for each in nodes
            for name, own in imported_functions(each).items()
        },
    )


def calls_subprocess(node: ast.AST, names: Set[str], bound: Bindings) -> bool:
    """Whether a node is a call of a function of the ``subprocess`` module.

    Args:
        node: any node.
        names: the functions.
        bound: what the file's imports bind to the module.

    Returns:
        True for ``subprocess.run(...)``, ``sp.run(...)`` after
        ``import subprocess as sp``, and ``run(...)`` after
        ``from subprocess import run``.
    """
    if not isinstance(node, ast.Call):
        return False
    function = node.func
    if isinstance(function, ast.Attribute):
        return (
            isinstance(function.value, ast.Name)
            and function.value.id in bound.modules
            and function.attr in names
        )
    return (
        isinstance(function, ast.Name) and bound.functions.get(function.id, "") in names
    )


def mentions(node: ast.AST) -> Set[str]:
    """Every name and attribute a piece of syntax uses.

    Args:
        node: the syntax.

    Returns:
        The names.
    """
    return {
        x.id if isinstance(x, ast.Name) else x.attr
        for x in ast.walk(node)
        if isinstance(x, (ast.Name, ast.Attribute))
    }
