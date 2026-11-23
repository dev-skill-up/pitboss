"""The proofs that no count of rounds reaches the owner (keyword: ruling-typed).

Each takes the parsed package and returns its findings, one line each, empty when
it holds; ``CASES`` pairs each with the seed that breaks it (pitboss#517).
"""

import ast
from typing import Sequence

from .proofcase import Case, added, called_once
from .proofsource import Package, nodes

OWNER_STEP = "PAUSE_FOR_OWNER"


def no_pause_step(package: Package) -> Sequence[str]:
    """R1.1: no step pauses a PR for the owner by a count of rounds.

    Args:
        package: the package.

    Returns:
        Each place that names a ``PAUSE_FOR_OWNER`` step or builds one.
    """
    return [
        f"R1.1: {where}:{getattr(node, 'lineno', 0)} names {OWNER_STEP}"
        for where, node in nodes(package)
        if (isinstance(node, ast.Attribute) and node.attr == OWNER_STEP)
        or (isinstance(node, ast.Name) and node.id == OWNER_STEP)
        or (isinstance(node, ast.FunctionDef) and node.name == "pause_for_owner")
    ]


CASES = {
    "R1.1": Case(
        proof=no_pause_step,
        seed=added("flow.py", "def pause_for_owner() -> None:\n    return None"),
    ),
    "R1.2": Case(
        proof=called_once("R1.2", "steps.ruling_escalates", "rulingafter"),
        seed=added("flow.py", "OWNER = steps.ruling_escalates()"),
    ),
}
