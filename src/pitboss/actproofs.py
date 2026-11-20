"""The proofs of the act verbs: P8 (plan 6.3, keyword: one-path).

Each takes the parsed package and returns its findings, one line each, empty when
the property holds; ``CASES`` pairs each with the seed that breaks it.
"""

import ast
from typing import Mapping, Sequence

from . import proofsource, worldfields
from .proofcase import Case, added, edited
from .proofsource import Package


def act_decisions_typed(package: Package) -> Sequence[str]:
    """P8.1: the act verbs' questions hold the typed decisions (``Decisions``).

    Args:
        package: the package.

    Returns:
        What ``Decisions`` is and ``Questions`` holds, when not the type.
    """
    core = proofsource.module(package, "actcore")
    aliases = {
        target.id: ast.unparse(node.value)
        for node in proofsource.statements(core)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    held = [
        ast.unparse(each.annotation)
        for each in worldfields.fields(core, "Questions")
        if worldfields.field_name(each) == "decided"
    ]
    wanted = "Callable[[actport.Asked], answer.Decided]"
    ok = aliases.get("Decisions") == wanted and held == ["Decisions"]
    return (
        []
        if ok
        else [f"P8.1: Decisions is {aliases.get('Decisions')}, Questions holds {held}"]
    )


def _ends_total(body: Sequence[ast.stmt]) -> bool:
    # a match on a verb ends in ``assert_never``, or hands the verbs it leaves to
    # the next group's match (the last group of the chain ends in ``assert_never``)
    last = body[-1] if body else None
    handed = last.value if isinstance(last, ast.Return) and last.value else None
    return proofsource.ends_never(body) or (
        handed is not None and proofsource.called(handed).startswith("applied_to_")
    )


def act_lookup_total(package: Package) -> Sequence[str]:
    """P8.2: the act lookup is a total match: each arm hands on or is never.

    Args:
        package: the package.

    Returns:
        Each match on a verb that is not.
    """
    return [
        f"P8.2: {short}:{node.lineno} matches a verb without assert_never"
        for short, node in proofsource.nodes(package)
        if short == "actverbs"
        and isinstance(node, ast.Match)
        and "verb" in ast.unparse(node.subject)
        and not _ends_total(node.cases[-1].body)
    ]


def no_total_verdict(package: Package) -> Sequence[str]:
    """P8.3: there is no ``totalverdict`` module.

    Args:
        package: the package.

    Returns:
        A finding when there is.
    """
    return [
        "P8.3: totalverdict exists"
        for name in package.sources
        if proofsource.short(name) == "totalverdict"
    ]


CASES: Mapping[str, Case] = {
    "P8.1": Case(
        proof=act_decisions_typed,
        seed=edited(
            "actcore.py",
            "Decisions = Callable[[actport.Asked], answer.Decided]",
            "Decisions = Callable[[actport.Asked], int]",
        ),
    ),
    "P8.2": Case(
        proof=act_lookup_total,
        seed=added(
            "actverbs.py",
            "def looked_up(verb: str) -> int:\n    match verb:\n        case 'a':\n"
            "            return 1\n        case _:\n            return 2",
        ),
    ),
    "P8.3": Case(proof=no_total_verdict, seed=added("totalverdict.py", "GATE = 1")),
}
