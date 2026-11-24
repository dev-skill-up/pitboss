"""The proofs that every act verb is answered by the decision (P8.4, P8.5; #524).

Each takes the parsed package and returns its findings, one line each, empty when
the property holds; ``CASES`` pairs each with the seed that breaks it. A verb is
applied only through ``actverbs.run``, which looks the verb's answer up in the
decisions (``gateverbs.lookup``) and returns before it applies the verb when
something else stands (``_stands``): the gate of a command is that lookup.
"""

import ast
import itertools
from typing import Mapping, Sequence

from . import proofsource
from .proofcase import Case, added, edited
from .proofsource import Package

TABLE = "actverbs.VERBS"  # the table of what applies each verb
ALLOWED = frozenset({"run", "VERBS", "REFUSALS"})  # what other modules take of actverbs


def _before_the_table(run: ast.FunctionDef) -> Sequence[str]:
    # the steps of ``run`` that come before the line that applies a verb
    before = list(
        itertools.takewhile(lambda each: "table[" not in ast.unparse(each), run.body)
    )
    looked = [
        "lookup"
        for each in before
        if isinstance(each, ast.Assign) and "gateverbs.lookup(" in ast.unparse(each)
    ]
    stopped = [
        "returns"
        for each in before
        if isinstance(each, ast.If)
        and "_stands(" in ast.unparse(each.test)
        and any(isinstance(inner, ast.Return) for inner in each.body)
    ]
    return [*looked, *stopped]


def run_looks_up_first(package: Package) -> Sequence[str]:
    """P8.4: ``run`` looks the verb up, and returns before it applies it when it stands.

    Args:
        package: the package.

    Returns:
        A finding when ``actverbs.run`` applies a verb before both.
    """
    run = proofsource.defined(package, "actverbs", "run")
    steps = _before_the_table(run) if run else []
    return (
        []
        if steps == ["lookup", "returns"]
        else [f"P8.4: actverbs.run applies a verb after {steps or 'nothing'}"]
    )


def _outside(short: str, node: ast.AST) -> str:
    # what a module other than actverbs does with the verbs' table or a handler
    if not isinstance(node, ast.Attribute) or short == "actverbs":
        return ""
    if not proofsource.dotted(node).startswith("actverbs.") or node.attr in ALLOWED:
        return ""
    return f"P8.5: {short}:{node.lineno} takes actverbs.{node.attr}"


def only_run_applies(package: Package) -> Sequence[str]:
    """P8.5: no module takes a handler of a verb, or an entry of the table.

    Args:
        package: the package.

    Returns:
        Each module that names a part of ``actverbs`` other than ``run``, the table
        and the refusals, or reads an entry of the table.
    """
    found = [_outside(short, node) for short, node in proofsource.nodes(package)]
    entries = [
        f"P8.5: {short}:{node.lineno} reads an entry of {TABLE}"
        for short, node in proofsource.nodes(package)
        if short != "actverbs"
        and isinstance(node, ast.Subscript)
        and proofsource.dotted(node.value) == TABLE
    ]
    return [each for each in (*found, *entries) if each]


CASES: Mapping[str, Case] = {
    "P8.4": Case(
        proof=run_looks_up_first,
        seed=edited(
            "actverbs.py",
            "    if _stands(verb, found, asked, item):",
            "    if verb is None:",
        ),
    ),
    "P8.5": Case(
        proof=only_run_applies,
        seed=added(
            "actrogue.py",
            "from . import actverbs\n\nHANDLER = actverbs.applied_to_item\n",
        ),
    ),
}
