"""The static proofs of the one path, run by ``nox -s lint`` (plan section 6.3).

``python -m pitboss.pathproofs`` reads ``src/pitboss`` from the current directory,
runs P1 to P11 but P4 (the ``modes`` session) and prints each finding; the
status is 1 when there is one. It parses the package and runs none of its code
(keyword: one-path).
"""

import ast
import pathlib
import sys
from typing import Callable, Mapping, Sequence

from . import decideproofs, proofsource, readproofs
from .proofsource import Package

Proof = Callable[[Package], Sequence[str]]


def _aliases(package: Package) -> Mapping[str, Sequence[str]]:
    # each union a module names: ``answer.Answer`` is Work or NotEnoughWork
    found: dict[str, Sequence[str]] = {}
    for name in ("answer", "project"):
        for node in proofsource.statements(proofsource.module(package, name)):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.BinOp):
                members = ast.unparse(node.value).split(" | ")
                for target in node.targets:
                    found[f"{name}.{proofsource.dotted(target)}"] = [
                        each if "." in each else f"{name}.{each}" for each in members
                    ]
    return found


def _given(name: str, annotation: ast.expr | None) -> str:
    said = "" if annotation is None else ast.unparse(annotation)
    return f"{name}.{said}" if said.isidentifier() and said[0].isupper() else said


def _projected(package: Package) -> Sequence[str]:
    return [
        _given("project", each.returns)
        for name, each in proofsource.functions_of(package, "project").items()
        if not name.startswith("_")
    ]


def _renderers(package: Package, returned: Sequence[str]) -> Sequence[str]:
    # each public renderer whose first argument is no projection's value
    aliases = _aliases(package)
    allowed = {*returned, *(m for each in returned for m in aliases.get(each, ()))}
    found = []
    for name, function in proofsource.functions_of(package, "render").items():
        first = function.args.args[0].annotation if function.args.args else None
        given = _given("render", first)
        if not name.startswith("_") and given not in allowed:
            found.append(f"P5: render.{name} takes {given}, no projection's value")
    return found


def _projections_given(package: Package) -> Sequence[str]:
    # each call of a projection given anything but the decisions as decided
    asked = {f"project.{each}" for each in proofsource.functions_of(package, "project")}
    found = []
    for short, node in proofsource.nodes(package):
        if proofsource.called(node) in asked and isinstance(node, ast.Call):
            argument = proofsource.first_argument(node)
            given = "" if argument is None else proofsource.dotted(argument)
            if not given.endswith("decided"):
                found.append(f"P5: {short}:{node.lineno} projects {given or 'a call'}")
    return found


def same_answer(package: Package) -> Sequence[str]:
    """P5: one projection a question; a renderer takes a projection's value.

    Args:
        package: the package.

    Returns:
        Each question with two projections, each renderer that takes another
        type, and each projection given anything but the decisions as decided.
    """
    returned = _projected(package)
    return [
        *(
            f"P5: two projections answer {each}"
            for each in sorted(set(returned))
            if returned.count(each) > 1
        ),
        *_renderers(package, returned),
        *_projections_given(package),
    ]


PROOFS: Mapping[str, Proof] = {
    "P1": decideproofs.one_decider,
    "P2": readproofs.no_io,
    "P3": decideproofs.no_partial_world,
    "P5": same_answer,
    "P6": readproofs.one_read,
    "P7": decideproofs.no_wait,
    "P8": decideproofs.act_agrees,
    "P9": readproofs.small_read,
    "P10": readproofs.stop_counts_decisions,
    "P11": readproofs.retried_once,
}


def findings(package: Package) -> Sequence[str]:
    """Every finding of every proof.

    Args:
        package: the package.

    Returns:
        The findings, proof by proof.
    """
    return [each for proof in PROOFS.values() for each in proof(package)]


def main(root: pathlib.Path) -> int:
    """Run the proofs on the package under a repository's root.

    Args:
        root: the root.

    Returns:
        0 when every proof holds, 1 otherwise.
    """
    found = findings(proofsource.package_at(root))
    for each in found:
        print(each)
    print("path proofs: ok" if not found else f"path proofs: {len(found)} findings")
    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(pathlib.Path.cwd()))
