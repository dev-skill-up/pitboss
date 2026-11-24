"""The capability rule: only capability packages reach the world (capability, #524).

``python -m pitboss.capability`` reads every ``.py`` file under the repository (not the
import graph, so a new package is read too) and says each place a module outside the
capability packages could read or change the world: an import that is not on the
allowlist, a banned name, a banned way to reach one without writing it, a string that
names a dunder, a runtime branch under ``TYPE_CHECKING`` and a use of the
``args.world`` the shell hands every command (processes and the environment). Each
finding is one line, ``path:line rule: what``; the exit status is the count's truth:
0 when there are none. The rules and what each closes are in the ticket
(dev-skill-up/pitboss#524).
"""

import ast
import dataclasses
import pathlib
import sys
from typing import AbstractSet, Callable, Iterator, Mapping, Sequence

from . import capabilityinputs, capabilitypure, capabilityset, importgraph
from .capabilitywords import (
    ALLOWED,
    BANNED_ATTRIBUTES,
    BANNED_CALLS,
    BANNED_METHODS,
    FRAMEWORK,
    MODULE_FILE,
    WORLD_MODULES,
)

# the modules that may reach the world are ``capabilityset.LISTED``; nothing else may.
# The decision (`decide`, the gate and the flow) is these modules and their imports:
# none of those may be a listed module but the ones that read what pitboss ships.
DECISION_ROOTS = (
    "pitboss.decide",
    "pitboss.gate",
    "pitboss.flow",
    "pitboss.gateverbs",
    "pitboss.actdecide",
    "pitboss.answer",
)
# the files pitboss ships (``phrases.shipped_text``, ``enumeration.shipped``: the
# version pitboss is) and the package itself (its version and entry data)
READS_FOR_THE_DECISION = frozenset(
    {"pitboss.phrases", "pitboss.enumeration", "pitboss"}
)


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


def _made(path: str, node: ast.AST, rule: str, what: str) -> Finding:
    return Finding(path=path, line=getattr(node, "lineno", 0), rule=rule, what=what)


# the key of WORLD_MODULES that is the name or a package of it, longest first
def _world_key(name: str) -> str | None:
    found = (each for each in importgraph.parents_of(name) if each in WORLD_MODULES)
    return max(found, key=len, default=None)


def _allowed(name: str) -> bool:
    return any(name == each or name.startswith(each + ".") for each in ALLOWED)


def _imports(path: str, node: ast.AST) -> Iterator[Finding]:
    match node:
        case ast.Import(names=names):
            found = [(each.name, "") for each in names]
        case ast.ImportFrom(module=module, names=names, level=0):
            found = [(module or "", each.name) for each in names]
        case _:
            found = []
    for module, name in found:
        key = _world_key(module)
        if _allowed(module) or (key and (not name or name in WORLD_MODULES[key])):
            continue
        yield _made(path, node, "E1", f"imports {name or module} from {module}")


def _banned_names(path: str, node: ast.AST) -> Iterator[Finding]:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in BANNED_CALLS:
            yield _made(path, node, "E3", f"calls {node.func.id}")


def _banned_methods(path: str, node: ast.AST) -> Iterator[Finding]:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in BANNED_METHODS:
            yield _made(path, node, "E3", f"calls .{node.func.attr}")


def _attributes(path: str, node: ast.AST) -> Iterator[Finding]:
    if not isinstance(node, ast.Attribute):
        return
    handed = isinstance(node.value, ast.Name) and node.value.id == "args"
    said = (
        (node.attr in BANNED_ATTRIBUTES, "E3", f"uses .{node.attr}"),
        (node.attr in FRAMEWORK and handed, "E1", f"uses args.{node.attr}"),
    )
    for found, rule, what in said:
        if found:
            yield _made(path, node, rule, what)


def _dunder_strings(path: str, node: ast.AST) -> Iterator[Finding]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        named = not MODULE_FILE.match(node.value)  # a path to a package's own file
        if named and "__" in node.value and node.value.strip("_") != "":
            yield _made(path, node, "E3", "a string names a dunder")


# whether a node is the name ``word``, or an attribute of that name
def _says(node: ast.AST, word: str) -> bool:
    return word in (getattr(node, "id", ""), getattr(node, "attr", ""))


def _type_checking(path: str, node: ast.AST) -> Iterator[Finding]:
    branched = isinstance(node, ast.If) and bool(node.orelse)
    if branched and _says(getattr(node, "test", node), "TYPE_CHECKING"):
        yield _made(path, node, "E3", "runtime code under TYPE_CHECKING")


# E14: a Step is named by its member, never made from a string that is read at run time
def _step_by_text(path: str, node: ast.AST) -> Iterator[Finding]:
    looked = isinstance(node, ast.Subscript) and _says(node.value, "Step")
    made = isinstance(node, ast.Call) and _says(node.func, "Step") and bool(node.args)
    if looked or made:
        yield _made(path, node, "E14", "names a Step by a value")


RULES: Sequence[Callable[[str, ast.AST], Iterator[Finding]]] = (
    _imports,
    _banned_names,
    _banned_methods,
    _attributes,
    _dunder_strings,
    _type_checking,
    _step_by_text,
)


# the world modules a file binds, by the name it uses for each (``from os import path``
# binds ``os.path``, as ``import os.path as path`` does)
def _aliases(tree: ast.AST) -> Mapping[str, str]:
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for each in node.names:
                bound[each.asname or each.name.split(".")[0]] = (
                    each.name if each.asname else each.name.split(".")[0]
                )
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            bound.update(_submodules(node.module, node.names))
    return bound


# ``from os import path``: the names of an import that are submodules of the world
def _submodules(module: str, names: Sequence[ast.alias]) -> Mapping[str, str]:
    dotted = {each.asname or each.name: f"{module}.{each.name}" for each in names}
    known = {*capabilitypure.PURE_NAMES, *WORLD_MODULES}
    return {name: full for name, full in dotted.items() if full in known}


# the module a name or a dotted name stands for, through the aliases
def _module_of(node: ast.expr, bound: Mapping[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return bound.get(node.id)
    if isinstance(node, ast.Attribute):
        base = _module_of(node.value, bound)
        dotted = f"{base}.{node.attr}"
        return dotted if base and dotted in capabilitypure.PURE_NAMES else None
    return None


# each use of an imported world module that is not one of its safe names; a
# submodule with pure names is used only through one of them
def _uses(path: str, tree: ast.AST) -> Iterator[Finding]:
    bound = _aliases(tree)
    inner = {
        id(node.value) for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        module = _module_of(node.value, bound)
        if module is None:
            continue
        pure = capabilitypure.PURE_NAMES.get(module)
        key = module if pure is not None else _world_key(module)
        allowed = pure if pure is not None else WORLD_MODULES.get(key or "", None)
        bare = (
            f"{module}.{node.attr}" in capabilitypure.PURE_NAMES
            and id(node) not in inner
        )
        if allowed is not None and (node.attr not in allowed or bare):
            yield _made(path, node, "E1", f"uses {key}.{node.attr}")


# each use of a banned builtin that is not a call (``reader = open``: an alias)
def _aliases_of_banned(path: str, tree: ast.AST) -> Iterator[Finding]:
    called = {
        id(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in BANNED_CALLS and id(node) not in called:
                yield _made(path, node, "E3", f"names {node.id}")


# E8: the owner is no actor (a ruling of the owner, 2026-11-23: nothing waits on them)
def _owner(path: str, tree: ast.AST) -> Iterator[Finding]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Actor":
            for member in node.body:
                named = isinstance(member, ast.Assign) and any(
                    isinstance(each, ast.Name) and each.id == "OWNER"
                    for each in member.targets
                )
                if named:
                    yield _made(path, member, "E8", "Actor has an OWNER")


def _walk(path: str, tree: ast.AST) -> Iterator[Finding]:
    yield from _uses(path, tree)
    yield from _aliases_of_banned(path, tree)
    yield from _owner(path, tree)
    for node in ast.walk(tree):
        for rule in RULES:
            yield from rule(path, node)


def closure(edges: Mapping[str, AbstractSet[str]]) -> AbstractSet[str]:
    """The modules of the decision and everything they import, directly or not.

    Args:
        edges: the modules each module imports.

    Returns:
        The roots that exist and every module they reach.
    """
    seen: set[str] = set()
    todo = [each for each in DECISION_ROOTS if each in edges]
    while todo:
        module = todo.pop()
        if module not in seen:
            seen.add(module)
            todo.extend(edges.get(module, ()))
    return seen


def _decision(texts: Mapping[str, str]) -> Iterator[Finding]:
    # E12: a module the decision imports may not be one that reaches the world
    graph = importgraph.build_graph(texts)
    inside = closure(graph.edges)
    for path in sorted(capabilityset.LISTED):
        module = importgraph.module_of(path)
        if module in inside and module not in READS_FOR_THE_DECISION:
            yield Finding(
                path=path, line=1, rule="E12", what="in the imports of the decision"
            )
    for path in sorted(texts):
        if importgraph.module_of(path) in inside:
            yield from _injected(path, ast.parse(texts[path], filename=path))


def _second_reads() -> Iterator[Finding]:
    # E13: one input is read by one module (``capabilityinputs``)
    owners: dict[str, str] = {}
    for path, reading in sorted(capabilityinputs.INPUTS.items()):
        if reading in owners:
            what = f"reads {reading}, which {owners[reading]} reads"
            yield Finding(path=path, line=1, rule="E13", what=what)
        owners.setdefault(reading, path)


def _is_protocol(node: ast.ClassDef) -> bool:
    return any(_says(each, "Protocol") for each in node.bases)


def _is_method(node: ast.stmt) -> bool:
    return isinstance(node, ast.FunctionDef) and not any(
        ast.unparse(each) == "property" for each in node.decorator_list
    )


def _injected(path: str, tree: ast.AST) -> Iterator[Finding]:
    # E15: a Protocol with a method, in the decision's imports, is a reader handed in
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and _is_protocol(node):
            if any(_is_method(each) for each in node.body):
                yield _made(
                    path, node, "E15", f"{node.name} is a Protocol with a method"
                )


def _stale(path: str) -> Finding:
    # E11: a listed module reaches the world somewhere, else the line is stale
    return Finding(path=path, line=1, rule="E11", what="listed, and reaches nothing")


def check(texts: Mapping[str, str]) -> Sequence[Finding]:
    """What the files given could do to the world.

    Args:
        texts: the text of each file, by its path from the repository's root.

    Returns:
        Each finding, in order, for the files not listed as capability, a stale
        listing and a listed module in the decision's imports.
    """
    found: list[Finding] = []
    for path in sorted(texts):
        mine = list(_walk(path, ast.parse(texts[path], filename=path)))
        listed = path in capabilityset.LISTED
        found.extend([] if listed else mine)
        found.extend([_stale(path)] if listed and not mine else [])
    found.extend(_decision(texts))
    found.extend(_second_reads())
    return found


def _read(root: pathlib.Path) -> Mapping[str, str]:
    # every ``.py`` file under the root but the environment's and the build's
    skipped = {".venv", "build", ".git", "node_modules"}
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.py"))
        if not skipped & set(path.relative_to(root).parts)
    }


def main(root: pathlib.Path) -> int:
    """Print each finding under a root and say whether there are none.

    Args:
        root: the repository's root.

    Returns:
        0 when there is none, else 1.
    """
    texts = _read(root)
    gone = (
        Finding(path=each, line=1, rule="E11", what="listed, and no such file")
        for each in sorted(capabilityset.LISTED)
        if each not in texts
    )
    found = [*check(texts), *gone]
    for each in found:
        print(each)
    print(f"{len(found)} findings", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(pathlib.Path.cwd()))
