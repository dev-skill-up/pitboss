"""The proofs of the decider's side: P1 and P3 (plan section 6.3).

Each takes the parsed package and returns its findings, one line each, empty when
the property holds (keyword: one-path).
"""

import ast
from typing import Iterator, Sequence

from . import proofsource, worldfields
from .proofsource import Package


def one_decider(package: Package) -> Sequence[str]:
    """P1: ``decide.decide`` decides from one world and nothing else.

    Args:
        package: the package.

    Returns:
        What it takes, when that is not one ``world.World`` with no default.
    """
    decider = proofsource.defined(package, "decide", "decide")
    said = proofsource.taken(decider)
    if said == ["world.World"] and decider and not decider.args.defaults:
        return []
    return [f"P1: decide.decide takes {said}"]


_fields = worldfields.fields
_field_name = worldfields.field_name


def _caught(package: Package, name: str) -> Iterator[tuple[str, ast.ExceptHandler]]:
    for short, node in proofsource.nodes(package):
        if isinstance(node, ast.ExceptHandler) and node.type is not None:
            if proofsource.dotted(node.type).endswith(name):
                yield short, node


def read_failure(package: Package) -> Sequence[str]:
    """The one read failure: caught once, at the command entry.

    Args:
        package: the package.

    Returns:
        What breaks it (P3 and P11).
    """
    found = []
    caught = list(_caught(package, "ReadFailed"))
    if [short for short, _ in caught] != ["cli_parser"]:
        found.append(f"P3: ReadFailed is caught in {[s for s, _ in caught]}")
    return found


def no_partial_world(package: Package) -> Sequence[str]:
    """P3: no record ``World`` holds has a default; a failed read ends the command.

    Args:
        package: the package.

    Returns:
        Each default in the World's closure and each break of the one read failure.
    """
    return [*worldfields.defaults(package), *read_failure(package)]
