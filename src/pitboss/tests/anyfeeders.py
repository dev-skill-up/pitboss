"""The modules whose values reach the decision, from the types it consumes (#524).

The decision consumes ``world.World``. A type it consumes is a class named in the
annotation of a field or parameter of a type it consumes (through the aliases of
the closure's modules). A module outside the closure that makes an instance of
one of them, by the class or by its module, feeds the decision.
"""

import ast
from typing import AbstractSet, Mapping, MutableMapping, Sequence

ROOT = "World"


def parsed(texts: Mapping[str, str]) -> Mapping[str, ast.Module]:
    """Parse each module.

    Args:
        texts: each module's source, by its name.

    Returns:
        Each module's syntax tree.
    """
    return dict(zip(texts, map(ast.parse, texts.values())))


def _names(node: ast.AST) -> Sequence[str]:
    found: list[str] = []
    for each in ast.walk(node):
        if isinstance(each, ast.Name):
            found.append(each.id)
        elif isinstance(each, ast.Attribute):
            found.append(each.attr)
        elif isinstance(each, ast.Constant) and isinstance(each.value, str):
            found.append(each.value)
    return found


def _declared(
    trees: Mapping[str, ast.Module],
) -> tuple[Mapping[str, Sequence[ast.ClassDef]], Mapping[str, Sequence[ast.expr]]]:
    classes: MutableMapping[str, list[ast.ClassDef]] = {}
    aliases: MutableMapping[str, list[ast.expr]] = {}
    for module in trees.values():
        for each in ast.walk(module):
            if isinstance(each, ast.ClassDef):
                classes.setdefault(each.name, []).append(each)
        for each in module.body:
            if isinstance(each, ast.Assign) and isinstance(each.targets[0], ast.Name):
                aliases.setdefault(each.targets[0].id, []).append(each.value)
    return classes, aliases


def _annotated(node: ast.ClassDef) -> Sequence[str]:
    # the names in the annotations of the class's fields and parameters
    notes = [n.annotation for n in ast.walk(node) if isinstance(n, ast.arg)]
    notes += [n.annotation for n in ast.walk(node) if isinstance(n, ast.AnnAssign)]
    return [x for note in notes if note for x in _names(note)]


def consumed(trees: Mapping[str, ast.Module]) -> AbstractSet[str]:
    """The classes the decision consumes.

    Args:
        trees: the closure's modules, by name.

    Returns:
        The names of the classes reachable from ``World`` by annotation.
    """
    classes, aliases = _declared(trees)
    seen: set[str] = set()
    todo = [ROOT]
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        todo += [x for each in aliases.get(name, ()) for x in _names(each)]
        todo += [x for each in classes.get(name, ()) for x in _annotated(each)]
    return seen & set(classes)


def _imported(tree: ast.Module) -> Mapping[str, tuple[str, str | None]]:
    # a local name: its module, and the class it names (None for a module)
    local: dict[str, tuple[str, str | None]] = {}
    for each in [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]:
        if each.level != 1:
            continue
        for name in each.names:
            module = name.name if each.module is None else each.module
            kind = None if each.module is None else name.name
            local[name.asname or name.name] = (f"pitboss.{module}", kind)
    return local


def _makes(
    func: ast.expr,
    local: Mapping[str, tuple[str, str | None]],
    defined: Mapping[str, AbstractSet[str]],
) -> bool:
    if isinstance(func, ast.Name):
        module, target = local.get(func.id, ("", ""))
        return target in defined.get(module, ())
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        module, target = local.get(func.value.id, ("", ""))
        return target is None and func.attr in defined.get(module, ())
    return False


def _made(tree: ast.Module, defined: Mapping[str, AbstractSet[str]]) -> bool:
    local = _imported(tree)
    calls = [each.func for each in ast.walk(tree) if isinstance(each, ast.Call)]
    return any(_makes(func, local, defined) for func in calls)


def feeders(
    trees: Mapping[str, ast.Module], closure: AbstractSet[str]
) -> AbstractSet[str]:
    """The modules outside the closure that make a value the decision consumes.

    Args:
        trees: every module of the package, by name.
        closure: the decision's closure.

    Returns:
        Their names.
    """
    inside = {name: tree for name, tree in trees.items() if name in closure}
    wanted = consumed(inside)
    defined = {
        name: {
            each.name
            for each in ast.walk(tree)
            if isinstance(each, ast.ClassDef) and each.name in wanted
        }
        for name, tree in inside.items()
    }
    return {
        name
        for name, tree in trees.items()
        if name not in closure and _made(tree, defined)
    }
