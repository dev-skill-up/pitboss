"""The package as the static proofs read it (keyword: one-path, plan section 6.3).

The proofs P1 to P11 read the parsed text of ``src/pitboss`` without its tests,
and the import graph ``importgraph`` builds for ``lint change``. Nothing here runs
the package's code.
"""

import ast
import dataclasses
import pathlib
from typing import AbstractSet, Iterator, Mapping, Sequence, TypeVar

from . import importgraph

PACKAGE = "pitboss"
# the proofs name what they look for; their own text is not the package's
PROOFS = frozenset(
    {
        "pitboss.decideproofs",
        "pitboss.readproofs",
        "pitboss.pathproofs",
        "pitboss.proofseeds",
    }
)
Top = TypeVar("Top", ast.FunctionDef, ast.ClassDef)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Package:
    """The modules of the package, parsed, and what each imports.

    Attributes:
        sources: each module's parsed text, by its dotted name (no tests).
        edges: for each module, the modules of the package it imports.
    """

    sources: Mapping[str, importgraph.Source]
    edges: Mapping[str, AbstractSet[str]]


def of_texts(texts: Mapping[str, str]) -> Package:
    """The package of the files given.

    Args:
        texts: the text of each ``.py`` file, by its path from the repository's
            root (``src/pitboss/decide.py``).

    Returns:
        The package, without the tests.
    """
    found, _ = importgraph.parse(
        {path: text for path, text in texts.items() if importgraph.module_of(path)}
    )
    sources = {
        each.module: each for each in found if not importgraph.in_tests(each.module)
    }
    graph = importgraph.build_graph(texts)
    edges = {name: graph.edges.get(name, frozenset()) for name in sources}
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


def module(package: Package, name: str) -> ast.AST:
    """One module's parsed text.

    Args:
        package: the package.
        name: the module's name in the package (``decide``).

    Returns:
        Its syntax; an empty module when there is no such module, so a check
        of a module that is gone finds what it requires missing.
    """
    found = package.sources.get(f"{PACKAGE}.{name}")
    return ast.Module(body=[], type_ignores=[]) if found is None else found.syntax


def closure(package: Package, name: str) -> AbstractSet[str]:
    """The modules a module reaches through its imports, itself included.

    Args:
        package: the package.
        name: the module's name in the package.

    Returns:
        Their dotted names.
    """
    reached: set[str] = set()
    todo = [f"{PACKAGE}.{name}"]
    while todo:
        current = todo.pop()
        if current not in reached:
            reached.add(current)
            todo.extend(package.edges.get(current, ()))
    return reached


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


def calls_of(package: Package, names: AbstractSet[str]) -> Sequence[str]:
    """Where the package calls one of some names.

    Args:
        package: the package.
        names: the dotted names, as written at the call.

    Returns:
        ``module:line`` of each call.
    """
    return [
        f"{where}:{getattr(node, 'lineno', 0)}"
        for where, node in nodes(package)
        if called(node) in names
    ]


def sites(package: Package, owner: str, name: str) -> Sequence[str]:
    """Where the package calls a module's function or makes its class.

    Args:
        package: the package.
        owner: the module's name in the package (``answer``).
        name: the function or class (``NotEnoughWork``).

    Returns:
        ``module:line`` of each call, as ``owner.name`` or as ``name``.
    """
    return calls_of(package, {f"{owner}.{name}", name})


def first_argument(call: ast.Call) -> ast.expr | None:
    """The first positional argument of a call.

    Args:
        call: the call.

    Returns:
        The argument; None when it has none.
    """
    return call.args[0] if call.args else None


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


def _top(tree: ast.AST, kind: type[Top]) -> Mapping[str, Top]:
    return {each.name: each for each in statements(tree) if isinstance(each, kind)}


def functions(tree: ast.AST) -> Mapping[str, ast.FunctionDef]:
    """The functions defined at the top of a module.

    Args:
        tree: the module.

    Returns:
        Each by its name.
    """
    return _top(tree, ast.FunctionDef)


def classes(tree: ast.AST) -> Mapping[str, ast.ClassDef]:
    """The classes defined at the top of a module.

    Args:
        tree: the module.

    Returns:
        Each by its name.
    """
    return _top(tree, ast.ClassDef)


def functions_of(package: Package, name: str) -> Mapping[str, ast.FunctionDef]:
    """The functions defined at the top of one module of the package.

    Args:
        package: the package.
        name: the module's name in the package.

    Returns:
        Each by its name; none when there is no such module.
    """
    return functions(module(package, name))


def defined(package: Package, owner: str, name: str) -> ast.FunctionDef | None:
    """One function defined at the top of one module of the package.

    Args:
        package: the package.
        owner: the module's name in the package.
        name: the function's name.

    Returns:
        The function; None when there is none.
    """
    return functions_of(package, owner).get(name)


def _joined(node: ast.JoinedStr) -> str:
    return "".join(
        str(each.value) if isinstance(each, ast.Constant) else "{}"
        for each in node.values
    )


def every_node(tree: ast.AST) -> Sequence[ast.AST]:
    """Every node of a tree, the tree included.

    Args:
        tree: the tree.

    Returns:
        The nodes, in ``ast.walk``'s order.
    """
    return list(ast.walk(tree))


def texts_of(tree: ast.AST) -> Iterator[tuple[int, str]]:
    """Every string literal of a module, with its line; an f-string read whole.

    Args:
        tree: the module.

    Yields:
        The line and the text (an f-string's holes as ``{}``).
    """
    walked = every_node(tree)
    joined = [node for node in walked if isinstance(node, ast.JoinedStr)]
    inside = {id(part) for node in joined for part in node.values}
    for node in walked:
        if isinstance(node, ast.JoinedStr):
            yield node.lineno, _joined(node)
        elif isinstance(node, ast.Constant) and id(node) not in inside:
            if isinstance(node.value, str):
                yield node.lineno, node.value


def searched(package: Package) -> Iterator[tuple[str, int, str]]:
    """Every string literal of the package but the proofs' own.

    Args:
        package: the package.

    Yields:
        The module's short name, the line and the text.
    """
    for name, source in package.sources.items():
        literals = [] if name in PROOFS else texts_of(source.syntax)
        for line, text in literals:
            yield short(name), line, text
