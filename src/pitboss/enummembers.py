"""The members of an enum, read from a module's source (keyword: enum-members)."""

import ast
from typing import Sequence


def members(tree: ast.AST, name: str) -> Sequence[str]:
    """The names a class of a module assigns.

    Args:
        tree: the module.
        name: the class.

    Returns:
        The assigned names, in order.
    """
    return [
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == name
        for member in node.body
        if isinstance(member, ast.Assign)
        for target in member.targets
        if isinstance(target, ast.Name)
    ]
