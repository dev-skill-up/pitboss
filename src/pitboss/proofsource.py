"""The package as the static proofs read it (keyword: one-path, plan section 6.3).

P4 reads the parsed text of ``src/pitboss`` without its tests,
and the import graph ``importgraph`` builds for ``lint change``. Nothing here runs
the package's code.
"""

import ast
import dataclasses
import functools
import pathlib
from typing import AbstractSet, Iterator, Mapping, Sequence

from . import importgraph

PACKAGE = "pitboss"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Package:
    """The modules of the package, parsed, and what each imports.

    Attributes:
        sources: each module's parsed text, by its dotted name (no tests).
        edges: for each module, the modules of the package it imports.
    """

    sources: Mapping[str, importgraph.Source]
    edges: Mapping[str, AbstractSet[str]]


@functools.cache
def _source(path: str, text: str) -> importgraph.Source | None:
    # one file parsed once for the whole run: a proof's edit changes one file's text
    found, _ = importgraph.parse({path: text})
    return found[0] if found else None


@functools.cache
def _imports(source: importgraph.Source, known: AbstractSet[str]) -> AbstractSet[str]:
    # what a file imports of the package, read once for each file's text
    return frozenset(importgraph.imported_by(source, known))


def of_texts(texts: Mapping[str, str]) -> Package:
    """The package of the files given.

    Each file is parsed once for the run and what it imports is read once, so a
    package that differs from another in one file's text costs that one file.

    Args:
        texts: the text of each ``.py`` file, by its path from the repository's
            root (``src/pitboss/decide.py``).

    Returns:
        The package, without the tests.
    """
    parsed = [
        _source(path, text)
        for path, text in texts.items()
        if importgraph.module_of(path)
    ]
    found = [each for each in parsed if each is not None]
    known = frozenset(each.module for each in found)
    sources = {
        each.module: each for each in found if not importgraph.in_tests(each.module)
    }
    edges = {name: _imports(each, known) - {name} for name, each in sources.items()}
    return Package(sources=sources, edges=edges)


def read(root: pathlib.Path) -> Mapping[str, str]:
    """The text of every ``.py`` file of the package.

    Args:
        root: the repository's root.

    Returns:
        Each file's text, by its path from the root.
    """
    base = root / importgraph.SOURCE
    return {
        f"{importgraph.SOURCE}{path.relative_to(base).as_posix()}": path.read_text(
            encoding="utf-8"
        )
        for path in sorted(base.rglob("*.py"))
    }


def package_at(root: pathlib.Path) -> Package:
    """The package under a repository's root.

    Args:
        root: the root.

    Returns:
        The package, without the tests.
    """
    return of_texts(read(root))


def short(name: str) -> str:
    """A module's name in the package.

    Args:
        name: its dotted name (``pitboss.decide``).

    Returns:
        The name without the package (``decide``).
    """
    return name.removeprefix(f"{PACKAGE}.")


def nodes(package: Package) -> Iterator[tuple[str, ast.AST]]:
    """Every node of every module.

    Args:
        package: the package.

    Yields:
        The module's short name and the node.
    """
    for name, source in package.sources.items():
        for node in ast.walk(source.syntax):
            yield short(name), node


def called(node: ast.AST) -> str:
    """The name a call calls, as written (``answer.Decision``, ``open``).

    Args:
        node: a node.

    Returns:
        The dotted name; empty when the node is no call of a plain name.
    """
    if not isinstance(node, ast.Call):
        return ""
    return dotted(node.func)


def dotted(node: ast.AST) -> str:
    """A name or an attribute chain as written.

    Args:
        node: the expression.

    Returns:
        The dotted name; empty for any other expression.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = dotted(node.value)
        return f"{inner}.{node.attr}" if inner else ""
    return ""


def ends_never(body: Sequence[ast.stmt]) -> bool:
    """Whether a block ends in a call of ``assert_never``.

    Args:
        body: the block.

    Returns:
        True when its last statement is that call.
    """
    last = body[-1] if body else None
    return isinstance(last, ast.Expr) and called(last.value) == "assert_never"


def statements(tree: ast.AST) -> Sequence[ast.stmt]:
    """The statements at the top of a module.

    Args:
        tree: the module.

    Returns:
        Them; none for anything but a module.
    """
    return tree.body if isinstance(tree, ast.Module) else []
