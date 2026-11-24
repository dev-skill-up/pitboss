"""What every rule of the capability checker shares (capability, #524)."""

import ast
import dataclasses
from typing import AbstractSet, Mapping, Sequence


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Finding:
    """One place a module could reach the world.

    Attributes:
        path: the file.
        line: the line.
        rule: the rule's name.
        what: what was found.
    """

    path: str
    line: int
    rule: str
    what: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} {self.rule}: {self.what}"


def made(path: str, node: ast.AST, rule: str, what: str) -> Finding:
    """A finding at a node.

    Args:
        path: the file.
        node: the syntax; a node with no line is at line 0.
        rule: the rule's name.
        what: what was found.

    Returns:
        The finding.
    """
    return Finding(
        path=path,
        line=node.lineno if isinstance(node, (ast.stmt, ast.expr)) else 0,
        rule=rule,
        what=what,
    )


def reach(
    edges: Mapping[str, AbstractSet[str]], roots: Sequence[str]
) -> AbstractSet[str]:
    """The roots that exist and every module they reach.

    Args:
        edges: the modules each module imports.
        roots: the modules to start from.

    Returns:
        The roots that are in the graph, and everything they import.
    """
    seen: set[str] = set()
    todo = [each for each in roots if each in edges]
    while todo:
        module = todo.pop()
        if module not in seen:
            seen.add(module)
            todo.extend(edges.get(module, ()))
    return seen
