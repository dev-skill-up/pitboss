"""Every GitHub write has an act verb.

The agent's write tools and pitboss's own commands.

``tools`` reads the frozen tool list, the tool calls of the agent sessions and the
routes of ``act-routes.tsv``: a write tool a route names has a verb that exists, and
one no route names was never used. ``commands`` follows pitboss's own call graph
from each registered command to a GitHub write (``.mutate`` or ``store_of``): a
command that reaches one has a verb in ``ROUTE``.
"""

import ast
import collections
import dataclasses
import pathlib
import re
from typing import AbstractSet, Iterator, Mapping, Sequence

from .. import enumeration

GITHUB = "mcp__github__"
WRITE = (
    "create", "update", "delete", "merge", "enable", "disable", "add", "push", "fork",
    "request", "resolve", "unresolve", "run", "sub_issue_write", "issue_write",
    "pull_request_review_write", "actions_run_trigger",
)  # fmt: skip
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
WRITER_NAMES = frozenset({"mutate", "store_of"})
STORE_NAMES = frozenset({"store_of"})
ACT_COMMAND = frozenset({"act"})
ROUTE: Mapping[str, str] = {
    "body-head": "pr-edit",
    "cancel-stale-runs": "cancel",
    "pins-review": "review",
    "ruling": "comment",
    "expand": "comment-edit",
    "clean": "scratch-clean",
    "clean-worktrees": "scratch-clean",
    "case": "ticket-edit",
    "owner-pause": "label",
    "plan-check": "comment",
    "sweep": "scratch-clean",
}
Function = tuple[str, str]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Row:
    """One tool or command judged.

    Attributes:
        kind: ``read``, ``verb``, ``unused``, ``fires``, ``benign`` or ``UNCOVERED``.
        name: the tool or the command.
        why: what decided it.
    """

    kind: str
    name: str
    why: str


def _used() -> Mapping[str, int]:
    rows = (
        line.split("\t")
        for line in enumeration.lines_of(enumeration.shipped("tool-calls.tsv"))
    )
    return {fields[0]: int(fields[1]) for fields in rows}


def _routes() -> Sequence[Sequence[str]]:
    lines = enumeration.lines_of(enumeration.shipped("act-routes.tsv"))
    return [
        fields
        for fields in (line.split("\t") for line in lines)
        if len(fields) == 3 and fields[0] != "class"
    ]


def _tool(name: str, used: int, verbs: Mapping[str, object]) -> Row:
    if not name.startswith(WRITE):
        return Row(kind="read", name=name, why="")
    rows = [fields for fields in _routes() if name in fields[0]]
    routed_verbs = [
        each
        for fields in rows
        for each in re.findall(r"\bact ([a-z]+(?:-[a-z]+)*)", fields[2])
        if each != "line"
    ]
    if routed_verbs and all(each in verbs for each in routed_verbs):
        return Row(kind="verb", name=name, why="act " + ", act ".join(routed_verbs))
    if rows and "git push" in rows[0][2]:
        return Row(kind="verb", name=name, why="act push")
    if not used:
        return Row(kind="unused", name=name, why="0 uses: no step of the work needs it")
    return Row(kind="UNCOVERED", name=name, why=f"{used} uses and no verb")


def tools(verbs: Mapping[str, object]) -> Sequence[Row]:
    """Judge every GitHub tool of the frozen tool list.

    Args:
        verbs: the act verbs.

    Returns:
        A row for each tool.
    """
    used = _used()
    names = [
        each for each in enumeration.values("agent-tool") if each.startswith(GITHUB)
    ]
    return [
        _tool(each.removeprefix(GITHUB), used.get(each, 0), verbs)
        for each in sorted(names)
    ]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Graph:
    """pitboss's functions as a call graph.

    Attributes:
        calls: each function's references to other functions.
        writers: the functions with a write site.
        registered: each command's function.
    """

    calls: Mapping[Function, AbstractSet[Function]]
    writers: AbstractSet[Function]
    registered: Mapping[str, Function]


def _imports(tree: ast.Module) -> tuple[dict[str, str], dict[str, Function]]:
    packages, names = {}, {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            for alias in node.names:
                if node.module:
                    names[alias.asname or alias.name] = (
                        node.module.split(".")[0],
                        alias.name,
                    )
                else:
                    packages[alias.asname or alias.name] = alias.name
    return packages, names


def _references(
    module: str, function: ast.AST, imports: tuple[dict[str, str], dict[str, Function]]
) -> Iterator[Function]:
    packages, names = imports
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in packages
        ):
            yield (packages[node.value.id], node.attr)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            yield names.get(node.id, (module, node.id))


def _writes(function: ast.AST) -> bool:
    return any(_writes_here(node) for node in ast.walk(function))


def _writes_here(node: ast.AST) -> bool:
    # a use of the store's writer, by attribute or by name
    if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
        return node.attr in WRITER_NAMES
    return isinstance(node, ast.Name) and node.id in STORE_NAMES


def _registered(function: ast.FunctionDef | ast.AsyncFunctionDef) -> Iterator[str]:
    for decorator in function.decorator_list:
        for word in decorator.keywords if isinstance(decorator, ast.Call) else ():
            if word.arg == "name" and isinstance(word.value, ast.Constant):
                yield str(word.value.value)


def call_graph(source: pathlib.Path) -> Graph:
    """The call graph of pitboss's modules.

    Args:
        source: the folder of pitboss's modules.

    Returns:
        The graph; every reference to a function counts as a call (the safe side).
    """
    calls: collections.defaultdict[Function, set[Function]]
    calls = collections.defaultdict(set)
    writers: set[Function] = set()
    registered: dict[str, Function] = {}
    for path in sorted(source.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in (
            node for node in ast.walk(tree) if isinstance(node, FUNCTIONS)
        ):
            me = (path.stem, function.name)
            calls[me].update(_references(path.stem, function, _imports(tree)))
            registered.update((name, me) for name in _registered(function))
            writers.update([me] if _writes(function) and me[1] != "mutate" else [])
        for kind, methods in _methods(path.stem, tree):
            calls[kind].update(methods)
    return Graph(calls=calls, writers=writers, registered=registered)


def _methods(
    module: str, tree: ast.Module
) -> Iterator[tuple[Function, Sequence[Function]]]:
    # a class named is every one of its methods called (the safe side)
    for kind in ast.walk(tree):
        if isinstance(kind, ast.ClassDef):
            yield (module, kind.name), [
                (module, each.name) for each in kind.body if isinstance(each, FUNCTIONS)
            ]


def reaches(found: Graph, start: Function) -> Sequence[str]:
    """The chain from a function to a write site.

    Args:
        found: the graph.
        start: the function.

    Returns:
        The chain (``module.function`` each), or nothing when it reaches none.
    """
    path: dict[Function, Function | None] = {start: None}
    todo = [start]
    while todo:
        here = todo.pop()
        if here in found.writers:
            return _chain(path, here)
        for after in found.calls.get(here, ()):
            if after not in path:
                path[after] = here
                todo.append(after)
    return []


def _chain(path: Mapping[Function, Function | None], end: Function) -> Sequence[str]:
    # the functions from the start to the end, by the step each was reached from
    chain: list[str] = []
    step: Function | None = end
    while step:
        chain.append(".".join(step))
        step = path[step]
    return chain[::-1]


def _command(found: Graph, name: str, verbs: Mapping[str, object]) -> Row:
    me = found.registered.get(name)
    if me is None:
        return Row(kind="UNCOVERED", name=name, why="no function registers this name")
    chain = reaches(found, me)
    if not chain:
        return Row(
            kind="benign", name=name, why=f"{'.'.join(me)}: reaches no GitHub write"
        )
    if name in ACT_COMMAND:
        return Row(
            kind="fires", name=name, why="the write path: every verb runs the verdict"
        )
    return _verb_row(name, chain, verbs)


def _verb_row(name: str, chain: Sequence[str], verbs: Mapping[str, object]) -> Row:
    # a command that writes: fires when it is routed to a verb
    routed, last = ROUTE.get(name, ""), chain[-3:]
    if routed in verbs:
        return Row(
            kind="fires",
            name=name,
            why=f"writes ({' -> '.join(last)}): routed to act {routed}",
        )
    return Row(
        kind="UNCOVERED",
        name=name,
        why=f"writes ({' -> '.join(last)}): no act route",
    )


def commands(
    source: pathlib.Path, names: Sequence[str], verbs: Mapping[str, object]
) -> Sequence[Row]:
    """Judge pitboss's commands.

    Args:
        source: the folder of pitboss's modules.
        names: the commands.
        verbs: the act verbs.

    Returns:
        A row for each command.
    """
    found = call_graph(source)
    return [_command(found, name, verbs) for name in names]
