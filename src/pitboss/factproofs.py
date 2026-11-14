"""Plan 6.1 and 4.3: each fact of the one path is derived once (keyword: one-path).

The plan names the facts that several parsers derived (4.3: "CI is green", "which
pull request works on ticket T", "blocked", "held") and wants each parsed once into
one field (6.1). Each fact here has its owner, the module of its one derivation, and
the evidence any derivation of it must read. Evidence of a fact in another module
the one path reaches (what ``onepath`` and ``actverbs`` import) is a second one:

* checks: an ``any`` or ``all`` that reads a run's ``failed`` or ``finished``
  (``checkoutcome.result``, ``any_finished``, ``all_finished``);
* works on: a pattern of a closing keyword, ``fix`` (``pullnames.names``);
* blocked: a pattern of ``blocked`` (``blockedform.named``);
* held: a ``Hold`` made, a hold issue read (``holdparse.parse``).
"""

import ast
import dataclasses
import functools
import re
from typing import Callable, Mapping, Sequence

from . import proofsource
from .proofsource import Package

Evidence = Callable[[ast.AST], bool]  # whether a node reads the fact's evidence
ROOTS = ("onepath", "actverbs")  # the modules they import are the one path's


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Fact:
    """A fact of the one path and its one derivation.

    Attributes:
        owner: the module of the one function that derives it.
        evidence: whether a node reads what a derivation of it reads.
    """

    owner: str
    evidence: Evidence


def _aggregate(node: ast.AST) -> bool:
    # an ``any`` or ``all`` over runs that reads their outcome
    if proofsource.called(node) not in {"any", "all"}:
        return False
    read = {each.attr for each in ast.walk(node) if isinstance(each, ast.Attribute)}
    return bool(read & {"failed", "finished"})


def _pattern(word: str, node: ast.AST) -> bool:
    # a compiled pattern whose text names the word
    if proofsource.called(node) != "re.compile" or not isinstance(node, ast.Call):
        return False
    first = proofsource.first_argument(node)
    said = [] if first is None else [text for _, text in proofsource.texts_of(first)]
    return any(re.search(word, text, re.IGNORECASE) for text in said)


def _hold(node: ast.AST) -> bool:
    # a hold made: what a reading of an issue as a hold gives
    return proofsource.called(node).rpartition(".")[2] == "Hold"


# a closing keyword, a block; a list of key names (``Fixtures``, ``Blocked-by``) is none
WORDS = {"pullnames": r"fix(?:e[sd])?\b", "blockedform": "blocked(?!-by)"}
FACTS: Mapping[str, Fact] = {
    "checks": Fact(owner="checkoutcome", evidence=_aggregate),
    **{
        fact: Fact(owner=owner, evidence=functools.partial(_pattern, WORDS[owner]))
        for fact, owner in (("works on", "pullnames"), ("blocked", "blockedform"))
    },
    "held": Fact(owner="holdparse", evidence=_hold),
}


def one_fact(package: Package) -> Sequence[str]:
    """Plan 6.1: no module of the one path derives a fact its owner derives.

    Args:
        package: the package.

    Returns:
        A finding for each node of another module that reads a fact's evidence.
    """
    reached = {
        proofsource.short(each)
        for root in ROOTS
        for each in proofsource.closure(package, root)
    }
    return [
        f"6.1: {where}:{getattr(node, 'lineno', 0)} derives {name} again;"
        f" {made.owner} is its one derivation"
        for where, node in proofsource.nodes(package)
        if where in reached
        for name, made in FACTS.items()
        if where != made.owner and made.evidence(node)
    ]
