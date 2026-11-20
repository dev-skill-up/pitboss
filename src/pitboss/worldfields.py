"""P3 over the World's whole closure: no field of a type it holds has a default.

Plan 6.1: ``read_world`` returns ``World``, "frozen records with no field
default". A record is in the closure when ``World`` names it, or a record or an
alias in the closure names it, in a field's annotation or an alias's value
(a ``Callable``'s parameters and result too), followed through each module's own
imports (keyword: one-path).
"""

import ast
from typing import Iterator, Mapping, Sequence

from . import proofsource
from .proofsource import Package

Named = tuple[str, str]  # a module's name in the package, and a name in it
START: Named = ("world", "World")


def _imports(tree: ast.AST) -> Mapping[str, Named]:
    # each name a module imports from the package: a module, or a name in one
    found: dict[str, Named] = {}
    for node in proofsource.statements(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            for each in node.names:
                given = each.asname or each.name
                found[given] = (
                    (node.module, each.name) if node.module else (each.name, "")
                )
    return found


def _aliases(tree: ast.AST) -> Mapping[str, ast.expr]:
    # each module-level name bound to a type expression
    found: dict[str, ast.expr] = {}
    for node in proofsource.statements(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                found[target.id] = node.value
    return found


def _named(tree: ast.AST, owner: str, expression: ast.expr) -> Iterator[Named]:
    # the names of the package an annotation or alias names, a quoted one too
    imported = _imports(tree)
    for _, text in proofsource.texts_of(expression):
        yield from _named(tree, owner, ast.parse(text, mode="eval").body)
    for node in ast.walk(expression):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            found = imported.get(node.value.id)
            if found is not None and not found[1]:
                yield found[0], node.attr
        elif isinstance(node, ast.Name):
            yield imported.get(node.id, (owner, node.id))


def fields(tree: ast.AST, name: str) -> Sequence[ast.AnnAssign]:
    """The annotated fields of a class of a module.

    Args:
        tree: the module.
        name: the class.

    Returns:
        Its fields, none when the module has no such class.
    """
    found = proofsource.classes(tree).get(name)
    body = [] if found is None else found.body
    return [each for each in body if isinstance(each, ast.AnnAssign)]


def field_name(field: ast.AnnAssign) -> str:
    """The name a field binds.

    Args:
        field: the field.

    Returns:
        Its name.
    """
    return proofsource.dotted(field.target)


def _visit(package: Package, at: Named) -> tuple[Sequence[str], Sequence[Named]]:
    # the defaults of one record, and the names it reaches
    owner, name = at
    tree = proofsource.module(package, owner)
    if name not in proofsource.classes(tree):
        value = _aliases(tree).get(name)
        return [], [] if value is None else list(_named(tree, owner, value))
    held = fields(tree, name)
    found = [
        f"P3: {owner}.{name}.{field_name(each)} has a default"
        for each in held
        if each.value is not None and "ClassVar" not in ast.unparse(each.annotation)
    ]
    reached = [named for each in held for named in _named(tree, owner, each.annotation)]
    return found, reached


def defaults(package: Package) -> Sequence[str]:
    """Each field with a default of a record in the World's closure.

    Args:
        package: the package.

    Returns:
        One finding for each.
    """
    seen: set[Named] = set()
    todo: list[Named] = [START]
    found: list[str] = []
    while todo:
        current = todo.pop()
        if current in seen:
            continue
        seen.add(current)
        said, reached = _visit(package, current)
        found.extend(said)
        todo.extend(reached)
    return sorted(found)
