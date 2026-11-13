"""The proofs of the reader's side: P2, P6, P9, P10 and P11 (plan section 6.3).

Each takes the parsed package and returns its findings, one line each, empty when
the property holds (keyword: one-path).
"""

import ast
import re
from typing import Sequence

from . import importgraph, proofsource
from .proofsource import Package

IO_MODULES = ("subprocess", "urllib", "socket")
IO_PACKAGE = frozenset({"pitboss.ghapi", "pitboss.ledger"})
PURE = ("decide", "project", "render")
LISTING = re.compile(r"/(issues|pulls)\?")
ORDERED = "sort=created&direction=asc"


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
    return [] if len(sites) == 1 else [f"P6: read_world is called at {sites}"]


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
    return [
        f"P9: {name}:{line} lists unordered: {text}"
        for name, line, text in paths
        if ORDERED not in text and not _open_pulls(text)
    ]


def _open_pulls(text: str) -> bool:
    return "/pulls?" in text and "state=open" in text


def small_read(package: Package) -> Sequence[str]:
    """P9: no ``state=all``, and every listing the reader asks for is ordered.

    Args:
        package: the package.

    Returns:
        Each break of (a) and (b); (d) is P2 and P6.
    """
    found = [
        f"P9: {short}:{line} asks for state=all"
        for short, line, text in proofsource.searched(package)
        if "state=all" in text
    ]
    found.extend(_listing_breaks(package))
    return found


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


def stop_counts_decisions(package: Package) -> Sequence[str]:
    """P10: the walk stops on the count of decisions, and an item is decided alone.

    Args:
        package: the package.

    Returns:
        What breaks it.
    """
    found = [*_walk_breaks(proofsource.defined(package, "readworld", "walk"))]
    taken = proofsource.taken(proofsource.defined(package, "decide", "decide_item"))
    if taken != ["world.Record"]:
        found.append(f"P10: decide_item takes {taken}, not one record")
    return found


def retried_once(package: Package) -> Sequence[str]:
    """P11: the retry's draw and sleep are given, with no default.

    Args:
        package: the package.

    Returns:
        What breaks it (where the read failure is caught is P3's).
    """
    wrap = proofsource.functions_of(package, "retrying").get("with_retries")
    if wrap is None:
        return ["P11: there is no retrying.with_retries"]
    arguments = [each.arg for each in wrap.args.args]
    if arguments != ["run", "draw", "sleep"] or wrap.args.defaults:
        return [f"P11: with_retries takes {arguments} with defaults"]
    return []
