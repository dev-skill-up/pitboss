"""The proofs of the retry: P11 (plan 6.3, keyword: one-path).

Each takes the parsed package and returns its findings, one line each, empty when
the property holds; ``CASES`` pairs each with the seed that breaks it.
"""

import ast
from typing import Mapping, Sequence

from . import proofsource
from .proofcase import Case, Proof, Seed, added
from .proofsource import Package
from .pureproofs import caught_once


def _retry(package: Package) -> ast.FunctionDef | None:
    return proofsource.defined(package, "retrying", "with_retries")


def retry_wraps_one(package: Package) -> Sequence[str]:
    """P11.1: the retry wraps the one request function.

    Args:
        package: the package.

    Returns:
        Where ``with_retries`` is used, when that is not one place.
    """
    sites = proofsource.calls_of(
        package, frozenset({"with_retries", "retrying.with_retries"})
    )
    return [] if len(sites) == 1 else [f"P11.1: with_retries wraps at {sites}"]


def _no_default(name: str, bullet: str) -> Proof:
    def proof(package: Package) -> Sequence[str]:
        function = _retry(package)
        if function is None:
            return [f"{bullet}: there is no with_retries"]
        args = function.args
        defaulted = args.args[len(args.args) - len(args.defaults) :]
        return (
            [f"{bullet}: {name} has a default"]
            if name in [each.arg for each in defaulted]
            else []
        )

    return proof


def raised_in_retry(package: Package) -> Sequence[str]:
    """P11.4: the read failure is raised only in the retry.

    Args:
        package: the package.

    Returns:
        Each other place.
    """
    return [
        f"P11.4: {short}:{node.lineno} raises ReadFailed"
        for short, node in proofsource.nodes(package)
        if isinstance(node, ast.Raise)
        and node.exc is not None
        and proofsource.called(node.exc).endswith("ReadFailed")
        and short != "retrying"
    ]


def caught_in_entry(package: Package) -> Sequence[str]:
    """P11.5: the read failure is caught only at the command entry.

    Args:
        package: the package.

    Returns:
        Where it is caught, when that is not the command entry.
    """
    return [f"P11.5: {each[5:]}" for each in caught_once(package)]


CASES: Mapping[str, Case] = {
    "P11.1": Case(
        proof=retry_wraps_one,
        seed=added("render.py", "BAD = retrying.with_retries(None, None, None)"),
    ),
    "P11.2": Case(
        proof=_no_default("draw", "P11.2"),
        seed=Seed(
            path="retrying.py",
            old="def with_retries(run: KeywordRun, draw: Draw, sleep: Sleep)",
            new="def with_retries(run: KeywordRun, sleep: Sleep, draw: Draw = print)",
        ),
    ),
    "P11.3": Case(
        proof=_no_default("sleep", "P11.3"),
        seed=Seed(
            path="retrying.py",
            old="def with_retries(run: KeywordRun, draw: Draw, sleep: Sleep)",
            new="def with_retries(run: KeywordRun, draw: Draw, sleep: Sleep = print)",
        ),
    ),
    "P11.4": Case(
        proof=raised_in_retry,
        seed=added("render.py", "def bad():\n    raise ReadFailed('x')"),
    ),
    "P11.5": Case(
        proof=caught_in_entry,
        seed=added(
            "render.py", "try:\n    pass\nexcept retrying.ReadFailed:\n    pass"
        ),
    ),
}
