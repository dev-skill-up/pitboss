"""The decision's modules are held to ``--disallow-any-expr`` (keyword: any-expr)."""

import pathlib
import re
import tomllib
import unittest
from typing import AbstractSet

from hamcrest import assert_that, equal_to

from .. import capability, importgraph, typedreaders

ROOT = pathlib.Path("pyproject.toml").resolve().parent
SOURCES = ROOT / "src" / "pitboss"
# the package, and the one module that casts Any away
EXEMPT = {"pitboss", "pitboss.typedstd"}
RECORD = re.compile(r"\bshapes\.[A-Z]\w+\(|\bevidencesplit\.Comment\(")
READING = re.compile(r"json\.loads|totaljson\.(?:read|rows|whole)\(")


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
        for path in sorted(SOURCES.glob("*.py"))
    }
    graph = importgraph.build_graph(texts)
    return set(capability.closure(graph.edges)) - EXEMPT


def parsers() -> AbstractSet[str]:
    """The modules that read a response and make a record of the Observation.

    Returns:
        Their names.
    """
    found = set()
    for path in sorted(SOURCES.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if READING.search(text) and RECORD.search(text):
            found.add(f"pitboss.{path.stem}")
    return found


class TestAnyExpr(unittest.TestCase):
    """The override and the decision name the same modules."""

    def test_the_override_is_the_closure_and_the_readers(self) -> None:
        """What the override holds is what the decision imports and the readers."""
        assert_that(declared(), equal_to(decision() | typedreaders.READERS))

    def test_every_parser_of_a_record_is_a_listed_reader(self) -> None:
        """A module that parses a response into a record is held to the flag."""
        missing = parsers() - typedreaders.READERS - decision()
        assert_that(sorted(missing), equal_to([]))

    def test_each_listed_reader_still_parses_a_response(self) -> None:
        """A reader that parses nothing any more is a stale line."""
        stale = [
            each
            for each in sorted(typedreaders.READERS)
            if not READING.search(
                (SOURCES / f"{each.removeprefix('pitboss.')}.py").read_text(
                    encoding="utf-8"
                )
            )
        ]
        assert_that(stale, equal_to([]))
