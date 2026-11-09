"""What the scans of the tests share: files, findings and names (pitboss#402).

The two rules (keyword: captured-run) read the syntax of the files of the
tests. ``capturescan`` reads for a command whose output is kept, ``poolscan``
for a subprocess run from a pool or a thread.
"""

import ast
import dataclasses
import pathlib
from collections.abc import Mapping, Set

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


def calls_subprocess(node: ast.AST, names: Set[str]) -> bool:
    """Whether a node is a call of a function of the ``subprocess`` module.

    Args:
        node: any node.
        names: the functions.

    Returns:
        True for ``subprocess.run(...)`` and the like.
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == SUBPROCESS
        and node.func.attr in names
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
