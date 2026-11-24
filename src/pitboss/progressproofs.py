"""A decided step has an action that can make its own selecting fact false (keyword: ruling-progress).

pitboss#526 (bats-lang/dom#140): ``RULING_STEPS`` was selected while a ruling's body
edits did not show *literally* in the body, and no edit could make them show (the
worker had carried them in other words, and a review of the head said they hold).
The selecting fact of a ruling step is therefore never the text alone: where
``rulingtyped.carried`` judges the body, a review of a handed-back state after the
ruling (``_reviewed``) is the other way out, in one ``or`` with it.
"""

import ast
from typing import Mapping, Sequence

from .proofcase import Case, Seed
from .proofsource import Package, called, nodes

TEXT = "rulingtyped.carried"
WAY_OUT = "_reviewed"


def _names(node: ast.AST) -> set[str]:
    return {name for each in ast.walk(node) if (name := called(each))}


def ruling_text_has_a_way_out(package: Package) -> Sequence[str]:
    """P13.2: a call of ``rulingtyped.carried`` is in an ``or`` with ``_reviewed``.

    Args:
        package: the package.

    Returns:
        ``module:line`` of each call of it that is not.
    """
    covered = {
        id(call)
        for _, parent in nodes(package)
        if isinstance(parent, ast.BoolOp)
        and isinstance(parent.op, ast.Or)
        and WAY_OUT in _names(parent)
        for call in ast.walk(parent)
    }
    return [
        f"P13.2: {where}:{node.lineno} judges a ruling by its text alone"
        for where, node in nodes(package)
        if isinstance(node, ast.Call)
        and called(node) == TEXT
        and id(node) not in covered
        and not where.endswith("progressproofs")
    ]


CASES: Mapping[str, Case] = {
    "P13.2": Case(
        proof=ruling_text_has_a_way_out,
        seed=Seed(
            path="flowstate.py",
            old=" or _reviewed(pr, posted)\n    return None if seen and held",
            new="\n    return None if seen and held",
        ),
    ),
}
