"""The proofs of the read, the walk and the retry: P9, P10 and P11 (plan 6.3).

Each takes the parsed package and returns its findings, one line each, empty when
the property holds; ``CASES`` pairs each with the seed that breaks it (keyword:
one-path).
"""

import ast


import re


from typing import Mapping, Sequence


from . import proofsource


from .proofcase import Case, Proof, Seed, added, called_once, outside, taking


from .proofsource import Package

ORDERED = ("sort=created&direction=asc", "sort=created&order=asc")


def no_state_all(package: Package) -> Sequence[str]:
    """P9.1: no request path of the package asks for every state.

    Args:
        package: the package.

    Returns:
        Each place.
    """
    return [
        f"P9.1: {short}:{line} asks for every state"
        for short, line, text in proofsource.searched(package)
        if "state=" + "all" in text
    ]


def _listings(package: Package, kind: str) -> Sequence[tuple[str, int, str]]:
    # each request path of the reader's closure that lists ``issues`` or ``pulls``
    order = ("workorder", "pullsearch")  # the modules that list the order of work
    read = sorted(
        {
            n
            for start in order
            for n in proofsource.closure(package, start)
            if n in package.sources
        }
    )
    return [
        (proofsource.short(name), line, text)
        for name in read
        for line, text in proofsource.texts_of(package.sources[name].syntax)
        if re.search(kind, text) and "head=" not in text
    ]


def _ordered(bullet: str, pattern: str, exempt: Sequence[str]) -> Proof:
    # each listing path of the pattern is ordered by its creation, or is the exempt one
    def proof(package: Package) -> Sequence[str]:
        return [
            f"{bullet}: {name}:{line} lists unordered: {text}"
            for name, line, text in _listings(package, pattern)
            if not any(each in text for each in ORDERED)
            and not any(each in text for each in exempt)
        ]

    return proof


def one_listing_function(package: Package) -> Sequence[str]:
    """P9.4: every listing path of the order of work comes from one function.

    Args:
        package: the package.

    Returns:
        The modules that write a listing path, when they are not one.
    """
    where = sorted(
        {
            name
            for name, _, text in _listings(package, r"issues\?|pulls\?")
            if text.startswith(("repos/", "search/"))
        }
    )
    return [] if len(where) <= 1 else [f"P9.4: listing paths are written in {where}"]


def _calls_in(package: Package, owner: str, names: frozenset[str]) -> Sequence[str]:
    return [
        f"{where}:{getattr(node, 'lineno', 0)}"
        for where, node in proofsource.nodes(package)
        if proofsource.called(node) in names
    ]


EXAMINERS = frozenset(
    {"walking.reading.examiner.ticket", "walking.reading.examiner.pull"}
)


def examined_once(package: Package) -> Sequence[str]:
    """P9.5: an item's details are requested only by the one examine function.

    Args:
        package: the package.

    Returns:
        Each other call of an examiner.
    """
    sites = _calls_in(package, "readworld", EXAMINERS)
    elsewhere = outside("P9.5", sites, "readworld", "an item is examined at")
    return [
        *elsewhere,
        *([] if len(sites) == 2 else [f"P9.5: examiners are called at {sites}"]),
    ]


def _body(package: Package, owner: str, name: str) -> Sequence[ast.AST]:
    # every node of a function; none when it is gone
    found = proofsource.defined(package, owner, name)
    return proofsource.every_node(found) if found else []


def _walk(package: Package) -> Sequence[ast.AST]:
    return _body(package, "readworld", "walk")


def _tests(nodes: Sequence[ast.AST], kind: type) -> Sequence[str]:
    # the test of each statement of a kind (``ast.If``, ``ast.While``)
    return [
        ast.unparse(node.test)
        for node in nodes
        if isinstance(node, (ast.If, ast.While)) and isinstance(node, kind)
    ]


def _loops(package: Package) -> Sequence[str]:
    return _tests(_walk(package), ast.While)


def stop_is_the_count(package: Package) -> Sequence[str]:
    """P9.7: the walk's loop condition is the stop or the extent's named item.

    Args:
        package: the package.

    Returns:
        A finding when the walk loops on anything else.
    """
    loops = _loops(package)
    return (
        []
        if loops == ["not len(decisions) >= walking.stop"]
        else [f"P9.7: the walk loops while {loops}"]
    )


def blocker_place(package: Package) -> Sequence[str]:
    """P10.2: a blocker's place is the least of its own and its namers' places.

    Args:
        package: the package.

    Returns:
        A finding when ``order`` places an item more than once, which would not give
        it the first (the least) of its places.
    """
    tests = _tests(_body(package, "placing", "order"), ast.If)
    return (
        []
        if "current not in placed" in tests
        else ["P10.2: order does not place an item once, at its first place"]
    )


def place_in_one_function(package: Package) -> Sequence[str]:
    """P10.3: the place is computed in one function, ``placing.order``.

    Args:
        package: the package.

    Returns:
        Each call outside the reader, and any other public ``placing`` function.
    """
    sites = proofsource.calls_of(package, frozenset({"placing.order"}))
    others = [
        each
        for each in proofsource.functions_of(package, "placing")
        if each != "order" and not each.startswith("_")
    ]
    return [
        *outside("P10.3", sites, "readworld", "the order is made at"),
        *(f"P10.3: placing.{each} is a second place" for each in others),
    ]


def stop_counts_decisions(package: Package) -> Sequence[str]:
    """P10.5: the walk's stop compares the stop count with the length of the decisions.

    Args:
        package: the package.

    Returns:
        What the walk compares, when it is not that.
    """
    loops = _loops(package)
    held = [
        ast.unparse(node.annotation)
        for node in proofsource.assigned(_walk(package), "decisions")
    ]
    ok = loops == ["not len(decisions) >= walking.stop"] and held == [
        "list[answer.Decision]"
    ]
    return [] if ok else [f"P10.5: the loop runs while {loops}, counting {held}"]


CASES: Mapping[str, Case] = {
    "P9.1": Case(
        proof=no_state_all,
        seed=added("workorder.py", "PATH = 'repos/o/r/issues?state={}'".format("all")),
    ),
    "P9.2": Case(
        proof=_ordered("P9.2", r"search/issues\?|issues\?", ()),
        seed=added("workorder.py", "PATH = 'repos/o/r/issues?state=open'"),
    ),
    "P9.3": Case(
        proof=_ordered("P9.3", r"pulls\?", ("state=open",)),
        seed=added("workorder.py", "PATH = 'repos/o/r/pulls?state=closed'"),
    ),
    "P9.4": Case(
        proof=one_listing_function,
        seed=added(
            "workorder.py", "PATH = 'repos/o/r/issues?sort=created&direction=asc'"
        ),
    ),
    "P9.5": Case(
        proof=examined_once,
        seed=added(
            "readworld.py",
            "def another(walking, each):\n"
            "    return walking.reading.examiner.pull(each, [], ())",
        ),
    ),
    "P9.6": Case(
        proof=called_once("P9.6", "_examine", "readworld"),
        seed=added("render.py", "BAD = _examine(None, None)"),
    ),
    "P9.7": Case(
        proof=stop_is_the_count,
        seed=Seed(
            path="readworld.py",
            old="while not len(decisions) >= walking.stop:",
            new="while True:",
        ),
    ),
    "P10.1": Case(
        proof=taking("P10.1", "placing", "order", ["Sequence[str]", "Named"]),
        seed=Seed(
            path="placing.py",
            old="def order(rows: Sequence[str], named: Named)",
            new="def order(rows: Sequence[str], named: Named, more: int)",
        ),
    ),
    "P10.2": Case(
        proof=blocker_place,
        seed=Seed(
            path="placing.py", old="if current not in placed:", new="if current:"
        ),
    ),
    "P10.3": Case(
        proof=place_in_one_function,
        seed=added("render.py", "BAD = placing.order([], {})"),
    ),
    "P10.4": Case(
        proof=taking("P10.4", "decide", "decide_item", ["world.Record"]),
        seed=Seed(
            path="decide.py",
            old="def decide_item(record: world.Record)",
            new="def decide_item(record: world.Record, made: world.World)",
        ),
    ),
    "P10.5": Case(
        proof=stop_counts_decisions,
        seed=Seed(
            path="readworld.py",
            old="while not len(decisions) >= walking.stop:",
            new="while not len(walked.examined) >= walking.stop:",
        ),
    ),
}
