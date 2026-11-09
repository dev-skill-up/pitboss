"""What the names of a file mean, by module (keyword: captured-run, pitboss#402).

A function is told from another of the same name by the module it is in, so
the names two modules share are not one function.
"""

import ast
import dataclasses
import pathlib
from collections.abc import Mapping, Set

from . import scanning

Key = tuple[str, str]


def module_of(path: str) -> str:
    """The name a file is imported as, by its last word.

    Args:
        path: the file's name under the package.

    Returns:
        ``gitutil`` for ``gitutil.py``; the directory's name for an ``__init__.py``.
    """
    each = pathlib.PurePosixPath(path)
    inside = each.stem == "__init__" and each.parent.name
    return each.parent.name if inside else each.stem


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Scope:
    """What the names of one file mean.

    Attributes:
        own: the name the file is imported as.
        imported: the words the file imports as modules, by the name it uses.
        functions: the names it imports from a module, as (module, function).
        defined: the functions defined in it.
    """

    own: str
    imported: Mapping[str, str]
    functions: Mapping[str, Key]
    defined: Set[str]


def imported_words(node: ast.AST) -> Mapping[str, str]:
    """The modules an import statement binds, by the name used for them.

    Args:
        node: any node.

    Returns:
        Each word of ``import a.b.c`` for itself, and ``as x`` for the last;
        ``from pkg import name`` binds ``name``, which may be a module.
    """
    if not isinstance(node, (ast.Import, ast.ImportFrom)):
        return {}
    found: dict[str, str] = {}
    for each in node.names:
        words = each.name.split(".")
        found.update({word: word for word in words})
        found[each.asname or words[0]] = words[-1] if each.asname else words[0]
    return found


def imported_keys(node: ast.AST) -> Mapping[str, Key]:
    """The functions a ``from module import name`` statement binds.

    Args:
        node: any node.

    Returns:
        Each name, as (the last word of the module, the name); none for any
        other node or a relative import of the package itself.
    """
    if not (isinstance(node, ast.ImportFrom) and node.module):
        return {}
    where = node.module.split(".")[-1]
    return {(each.asname or each.name): (where, each.name) for each in node.names}


def scope_of(path: str, tree: ast.AST) -> Scope:
    """The scope of a file.

    Args:
        path: the file's name.
        tree: the parsed file.

    Returns:
        Its scope.
    """
    nodes = list(ast.walk(tree))
    return Scope(
        own=module_of(path),
        imported={k: v for each in nodes for k, v in imported_words(each).items()},
        functions={k: v for each in nodes for k, v in imported_keys(each).items()},
        defined={x.name for x in scanning.defs(tree)},
    )


def name_keys(scope: Scope, node: ast.Name) -> Set[Key]:
    """The functions a name may be.

    Args:
        scope: the scope of the file.
        node: the name.

    Returns:
        The function it imports, and the function of the file it is.
    """
    return {
        *([scope.functions[node.id]] if node.id in scope.functions else []),
        *([(scope.own, node.id)] if node.id in scope.defined else []),
    }


def attribute_keys(scope: Scope, node: ast.Attribute) -> Set[Key]:
    """The functions an attribute may be.

    Args:
        scope: the scope of the file.
        node: the attribute.

    Returns:
        The function of an imported module, or else of the file (a method).
    """
    base = node.value
    word = base.id if isinstance(base, ast.Name) else ""
    word = base.attr if isinstance(base, ast.Attribute) else word
    if word in scope.imported:
        return {(scope.imported[word], node.attr)}
    return {(scope.own, node.attr)} if node.attr in scope.defined else set()


def used_keys(scope: Scope, node: ast.AST) -> Set[Key]:
    """The functions a piece of syntax may use, each with the module it is in.

    A name is a function of the file or one it imports; ``m.f`` is the ``f`` of
    the module ``m`` when the file imports ``m``, and otherwise the ``f`` of the
    file if it has one (a method). A name of another module's is not followed.

    Args:
        scope: the scope of the file.
        node: the syntax.

    Returns:
        The (module, function) pairs.
    """
    found: set[Key] = set()
    for each in ast.walk(node):
        if isinstance(each, ast.Name):
            found |= name_keys(scope, each)
        elif isinstance(each, ast.Attribute):
            found |= attribute_keys(scope, each)
    return found
