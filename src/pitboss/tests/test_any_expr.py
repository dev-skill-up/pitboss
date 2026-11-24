"""The decision's modules are held to ``--disallow-any-expr`` (keyword: any-expr)."""

import pathlib
import tomllib
import unittest
from typing import AbstractSet

from hamcrest import assert_that, equal_to

from .. import capability, importgraph

ROOT = pathlib.Path("pyproject.toml").resolve().parent
# the package, and the one module that casts Any away
EXEMPT = {"pitboss", "pitboss.typedstd"}


def declared() -> AbstractSet[str]:
    """The modules the mypy override holds to ``disallow_any_expr``.

    Returns:
        Their names.
    """
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    names: set[str] = set()
    for each in config["tool"]["mypy"]["overrides"]:
        if each.get("disallow_any_expr") is True:
            names.update(each["module"])
    return names


def decision() -> AbstractSet[str]:
    """The modules the decision's roots import, directly or not.

    Returns:
        Their names, without the package and ``typedstd``.
    """
    texts = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "src" / "pitboss").glob("*.py"))
    }
    graph = importgraph.build_graph(texts)
    return set(capability.closure(graph.edges)) - EXEMPT


class TestAnyExpr(unittest.TestCase):
    """The override and the decision name the same modules."""

    def test_the_override_is_the_decisions_closure(self) -> None:
        """What the override holds is what the decision imports."""
        assert_that(declared(), equal_to(decision()))
