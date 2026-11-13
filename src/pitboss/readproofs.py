"""The proofs of the reader's side: P2, P6, P9, P10 and P11 (plan section 6.3).

Each takes the parsed package and returns its findings, one line each, empty when
the property holds (keyword: one-path).
"""

import ast
import re
from typing import Mapping, Sequence

from . import importgraph, proofsource
from .proofsource import Package

IO_MODULES = ("subprocess", "urllib", "socket")
IO_PACKAGE = frozenset({"pitboss.ghapi", "pitboss.ledger"})
PURE = ("decide", "project", "render")
LISTING = re.compile(r"/(issues|pulls)\?")
ORDERED = "sort=created&direction=asc"
WALK_LISTING = "labels="


def _io_of(package: Package, name: str) -> Sequence[str]:
    source = package.sources[name]
    imported = set(importgraph.imports_of(source.package, source.syntax))
    found = sorted(
        each
        for each in imported
        if each.split(".")[0] in IO_MODULES or each in IO_PACKAGE
    )
    opens = [
        node.lineno
        for node in ast.walk(source.syntax)
        if isinstance(node, ast.Call) and proofsource.called(node) == "open"
    ]
    return [*found, *(f"open at line {line}" for line in opens)]


def no_io(package: Package) -> Sequence[str]:
    """P2: the decide, projection and render modules reach no I/O.

    Args:
        package: the package.

    Returns:
        Each module they reach that imports I/O or calls ``open``.
    """
    return [
        f"P2: {start} reaches {name}, which uses {said}"
        for start in PURE
        for name in sorted(proofsource.closure(package, start))
        if name in package.sources
        for said in _io_of(package, name)
    ]


def one_read(package: Package) -> Sequence[str]:
    """P6: ``read_world`` is called once, and no command module imports ``ghapi``.

    Args:
        package: the package.

    Returns:
        Each other call site and each command module that imports it.
    """
    sites = proofsource.sites(package, "readworld", "read_world")
    found = [] if len(sites) == 1 else [f"P6: read_world is called at {sites}"]
    found.extend(
        f"P6: {name} imports ghapi"
        for name, source in sorted(package.sources.items())
        if _is_command(name)
        and "pitboss.ghapi"
        in set(importgraph.imports_of(source.package, source.syntax))
    )
    return found


def _is_command(name: str) -> bool:
    short = name.removeprefix("pitboss.")
    return short == "commands" or short.endswith("_commands")


def _paths(package: Package, names: Sequence[str]) -> Sequence[tuple[str, int, str]]:
    # every request path a module writes, f-strings read with their holes
    return [
        (proofsource.short(name), line, text)
        for name in names
        for line, text in proofsource.texts_of(package.sources[name].syntax)
        if LISTING.search(text)
    ]


def _listing_breaks(package: Package) -> Sequence[str]:
    read = sorted(
        n for n in proofsource.closure(package, "readworld") if n in package.sources
    )
    paths = _paths(package, read)
    found = [
        f"P9: {name}:{line} lists unordered: {text}"
        for name, line, text in paths
        if ORDERED not in text and not _open_pulls(text)
    ]
    walking = {
        _function_at(package, name, line)
        for name, line, text in paths
        if "/issues?" in text and WALK_LISTING in text
    }
    if len(walking) != 1:
        found.append(f"P9: the label listing is built in {sorted(walking)}")
    return found


def _open_pulls(text: str) -> bool:
    return "/pulls?" in text and "state=open" in text


def _function_at(package: Package, name: str, line: int) -> str:
    for function in proofsource.functions_of(package, name).values():
        if function.lineno <= line <= (function.end_lineno or function.lineno):
            return f"{name}.{function.name}"
    return f"{name}:{line}"


def _callers(package: Package, called: str) -> Sequence[str]:
    found = []
    for name, source in package.sources.items():
        short = proofsource.short(name)
        for function in proofsource.functions(source.syntax).values():
            if any(
                proofsource.called(node).split(".")[-1] == called
                for node in ast.walk(function)
            ):
                found.append(f"{short}.{function.name}")
    return sorted(found)


def small_read(package: Package) -> Sequence[str]:
    """P9: no ``state=all``; ordered listings from one function; one examine.

    Args:
        package: the package.

    Returns:
        Each break of (a) to (c); (d) is P2 and P6.
    """
    found = [
        f"P9: {short}:{line} asks for state=all"
        for short, line, text in proofsource.searched(package)
        if "state=all" in text
    ]
    found.extend(_listing_breaks(package))
    for examine, by in EXAMINED.items():
        callers = _callers(package, examine)
        if callers != by:
            found.append(f"P9: {examine} is called by {callers}")
    return found


# each item detail read, and the walk's functions that alone call it
EXAMINED = {
    "examine_pull": ["readworld._examine"],
    "examine_ticket": ["readworld._examine"],
    "_examine": ["readworld._named", "readworld._with_blockers"],
    "_with_blockers": ["readworld.walk"],
}


def _walk_breaks(walk: ast.FunctionDef | None) -> Sequence[str]:
    walked = proofsource.every_node(walk) if walk else []
    compared = [ast.unparse(node) for node in walked if isinstance(node, ast.Compare)]
    held = [
        ast.unparse(node.annotation)
        for node in walked
        if isinstance(node, ast.AnnAssign)
        and proofsource.dotted(node.target) == "decisions"
    ]
    found = []
    if "len(decisions) >= walking.stop" not in compared:
        found.append(f"P10: the walk's stop compares {compared}")
    if held != ["list[answer.Decision]"]:
        found.append(f"P10: the stop counts {held}, not decisions")
    return found


def _taken(function: ast.FunctionDef | None) -> Sequence[str]:
    given = function.args.args if function else []
    return [ast.unparse(each.annotation) for each in given if each.annotation]


def stop_counts_decisions(package: Package) -> Sequence[str]:
    """P10: the walk stops on the count of decisions, and an item is decided alone.

    Args:
        package: the package.

    Returns:
        What breaks it.
    """
    found = [*_walk_breaks(proofsource.defined(package, "readworld", "walk"))]
    taken = _taken(proofsource.defined(package, "decide", "decide_item"))
    if taken != ["world.Record"]:
        found.append(f"P10: decide_item takes {taken}, not one record")
    return found


def _raising(functions: Mapping[str, ast.FunctionDef]) -> Sequence[str]:
    return [
        name
        for name, function in functions.items()
        if any(
            isinstance(node, ast.Raise) and "ReadFailed" in ast.unparse(node)
            for node in ast.walk(function)
        )
    ]


def retried_once(package: Package) -> Sequence[str]:
    """P11: the retry wraps the one runner; its draw and sleep have no default.

    Args:
        package: the package.

    Returns:
        What breaks it (the read failure's own sites are P3's).
    """
    retrying = proofsource.functions_of(package, "retrying")
    wrap = retrying.get("with_retries")
    if wrap is None:
        return ["P11: there is no retrying.with_retries"]
    found = []
    arguments = [each.arg for each in wrap.args.args]
    if arguments != ["run", "draw", "sleep"] or wrap.args.defaults:
        found.append(f"P11: with_retries takes {arguments} with defaults")
    found.extend(
        f"P11: the retry wraps {wrapped_at}"
        for wrapped_at in [proofsource.sites(package, "retrying", "with_retries")]
        if len(wrapped_at) != 1
    )
    raised = _raising(retrying)
    if raised != ["_tries"]:
        found.append(f"P11: ReadFailed is raised in {raised}")
    return found
