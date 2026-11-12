"""Every GitHub write has an act verb: the agent's write tools and pitboss's own commands.

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
from typing import Iterator, Mapping, Sequence

from .. import enumeration

GITHUB = "mcp__github__"
WRITE = (
    "create", "update", "delete", "merge", "enable", "disable", "add", "push", "fork",
    "request", "resolve", "unresolve", "run", "sub_issue_write", "issue_write",
    "pull_request_review_write", "actions_run_trigger",
)  # fmt: skip
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
    named = [
        verb
        for fields in rows
        for verb in re.findall(r"\bact ([a-z]+(?:-[a-z]+)*)", fields[2])
        if verb != "line"
    ]
    if named and all(verb in verbs for verb in named):
        return Row(kind="verb", name=name, why="act " + ", act ".join(named))
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

    calls: Mapping[Function, set[Function]]
    writers: set[Function]
    registered: Mapping[str, Function]


def _imports(tree: ast.Module) -> tuple[dict[str, str], dict[str, Function]]:
    modules, names = {}, {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            for alias in node.names:
                if node.module:
                    names[alias.asname or alias.name] = (
                        node.module.split(".")[0],
                        alias.name,
                    )
                else:
                    modules[alias.asname or alias.name] = alias.name
    return modules, names


def _references(
    module: str, function: ast.AST, imports: tuple[dict[str, str], dict[str, Function]]
) -> Iterator[Function]:
    modules, names = imports
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in modules
        ):
            yield (modules[node.value.id], node.attr)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            yield names.get(node.id, (module, node.id))


def _writes(function: ast.AST) -> bool:
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Attribute)
            and node.attr in ("mutate", "store_of")
            and isinstance(node.ctx, ast.Load)
        ):
            return True
        if isinstance(node, ast.Name) and node.id == "store_of":
            return True
    return False


def _registered(function: ast.FunctionDef | ast.AsyncFunctionDef) -> Iterator[str]:
    for decorator in function.decorator_list:
        for word in decorator.keywords if isinstance(decorator, ast.Call) else ():
            if word.arg == "name" and isinstance(word.value, ast.Constant):
                yield str(word.value.value)


def graph(source: pathlib.Path) -> Graph:
    """The call graph of pitboss's modules.

    Args:
        source: the folder of pitboss's modules.

    Returns:
        The graph; every reference to a function counts as a call (the safe side).
    """
    calls: dict[Function, set[Function]] = collections.defaultdict(set)
    writers, registered = set(), {}
    for path in sorted(source.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = _imports(tree)
        for function in (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ):
            me = (path.stem, function.name)
            calls[me].update(_references(path.stem, function, imports))
            registered.update((name, me) for name in _registered(function))
            if _writes(function) and function.name != "mutate":
                writers.add(me)
        for kind in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
            # a class named is every one of its methods called (the safe side)
            methods = (
                node.name
                for node in kind.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
            calls[(path.stem, kind.name)].update((path.stem, name) for name in methods)
    return Graph(calls=calls, writers=writers, registered=registered)


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
            chain: list[str] = []
            step: Function | None = here
            while step:
                chain.append(".".join(step))
                step = path[step]
            return chain[::-1]
        for after in found.calls.get(here, ()):
            if after not in path:
                path[after] = here
                todo.append(after)
    return []


def _command(found: Graph, name: str, verbs: Mapping[str, object]) -> Row:
    me = found.registered.get(name)
    if me is None:
        return Row(kind="UNCOVERED", name=name, why="no function registers this name")
    chain = reaches(found, me)
    if not chain:
        return Row(
            kind="benign", name=name, why=f"{'.'.join(me)}: reaches no GitHub write"
        )
    if name == "act":
        return Row(
            kind="fires", name=name, why="the write path: every verb runs the verdict"
        )
    verb = ROUTE.get(name, "")
    if verb in verbs:
        return Row(
            kind="fires",
            name=name,
            why=f"writes ({' -> '.join(chain[-3:])}): routed to act {verb}",
        )
    return Row(
        kind="UNCOVERED",
        name=name,
        why=f"writes ({' -> '.join(chain[-3:])}): no act route",
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
    found = graph(source)
    return [_command(found, name, verbs) for name in names]
