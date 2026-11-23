"""A review step is constructible only from a standing (pitboss#507, standing).

The proof reads the parsed text of ``src/pitboss`` without its tests and runs none
of its code. It holds that ``steps.Standing`` is built only in ``standing.py``,
that a ``REGULAR_REVIEW`` step is built only in ``steps.regular_review``, whose
parameter is a ``Standing``, and that each call of ``regular_review`` passes a name
bound from ``standing.of``: no code of the package builds one by any of these
forms (a heuristic over the text, not a bar to a determined alias). The type
checker (``mypy src/pitboss``) holds the rest: ``regular_review`` takes nothing
else.
"""

import ast
import pathlib
import unittest
from typing import Iterator, Mapping, Sequence

from hamcrest import assert_that, empty, equal_to


def _read() -> Mapping[str, str]:
    # the package's files by their path from the repository's root
    package = pathlib.Path(__file__).parent.parent
    names = {
        each: each.relative_to(package).as_posix() for each in package.rglob("*.py")
    }
    return {f"src/pitboss/{name}": path.read_text() for path, name in names.items()}


TEXTS = _read()

STEPS = "src/pitboss/steps.py"
STANDING = "src/pitboss/standing.py"
FLOW = "src/pitboss/flow.py"
BUILDERS = frozenset({"Next", "replace", "partial", "evolve", "__replace__"})
GUARDED = "regular_review"
EMPTY = ast.Module(body=[], type_ignores=[])


def _trees(texts: Mapping[str, str]) -> Mapping[str, ast.Module]:
    return {
        path: ast.parse(text)
        for path, text in texts.items()
        if "/tests/" not in path and path.endswith(".py")
    }


def _nodes(tree: ast.AST) -> Iterator[tuple[ast.AST, str]]:
    # every node with the name of the function it is in ("" at module level)
    def under(node: ast.AST, name: str) -> Iterator[tuple[ast.AST, str]]:
        for child in ast.iter_child_nodes(node):
            inside = child.name if isinstance(child, ast.FunctionDef) else name
            yield child, inside
            yield from under(child, inside)

    yield from under(tree, "")


def _attribute(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == name


def _called(node: ast.AST) -> str:
    # the name a call is made by, "" for anything that is not a call
    if isinstance(node, ast.Call):
        return ast.unparse(node.func).rsplit(".", 1)[-1]
    return ""


def _given(node: ast.AST) -> Sequence[ast.AST]:
    # what a call is given, by position and by keyword
    if not isinstance(node, ast.Call):
        return []
    keyed = [each.value for each in node.keywords]
    return [*node.args, *keyed]


def _mentions(node: ast.AST, name: str) -> bool:
    return any(_attribute(each, name) for each in ast.walk(node))


def _standing_built(path: str, node: ast.AST) -> bool:
    # ``steps.Standing(...)`` or an import of ``Standing``, outside standing
    made = isinstance(node, ast.Call) and _attribute(node.func, "Standing")
    imported = isinstance(node, ast.ImportFrom) and any(
        each.name == "Standing" for each in node.names
    )
    return (made or imported) and path != STANDING


def _review_given(node: ast.AST) -> bool:
    # a builder given REGULAR_REVIEW
    given = [_mentions(each, "REGULAR_REVIEW") for each in _given(node)]
    return _called(node) in BUILDERS and any(given)


def _review_by_name(node: ast.AST) -> bool:
    # the member looked up by its name or its value
    lookup = isinstance(node, ast.Subscript) and _attribute(node.value, "Step")
    reflected = _called(node) == "getattr" and _mentions(node, "Step")
    by_value = _called(node) == "Step" and bool(getattr(node, "args", None))
    return lookup or reflected or by_value


def _signature(tree: ast.Module) -> Iterator[str]:
    found = [
        each
        for each in ast.walk(tree)
        if isinstance(each, ast.FunctionDef) and each.name == GUARDED
    ]
    if len(found) != 1:
        yield "steps has no single regular_review"
        return
    arguments = found[0].args
    kinds = [ast.unparse(each.annotation) for each in arguments.args if each.annotation]
    if kinds != ["Standing"] or len(arguments.args) != 1 or arguments.kwonlyargs:
        yield "regular_review does not take one Standing"


def _bound_from_of(function: ast.AST, name: str, made_by: str) -> bool:
    return any(
        isinstance(each, ast.Assign)
        and [ast.unparse(target) for target in each.targets] == [name]
        and isinstance(each.value, ast.Call)
        and ast.unparse(each.value.func) == made_by
        for each in ast.walk(function)
    )


def _unfounded(function: ast.AST, made_by: str) -> Iterator[int]:
    # the lines of calls whose argument is not a name bound from ``standing.of``
    for node in ast.walk(function):
        given = _given(node)
        only = ast.unparse(given[0]) if len(given) == 1 else ""
        if _called(node) == GUARDED and not _bound_from_of(function, only, made_by):
            yield getattr(node, "lineno", 0)


def _broken(path: str, node: ast.AST, inside: str) -> Iterator[str]:
    where = f"{path}:{getattr(node, 'lineno', 0)}"
    if _standing_built(path, node):
        yield f"{where} builds a Standing"
    guarded = (path, inside) == (STEPS, GUARDED)
    if (_review_given(node) or _review_by_name(node)) and not guarded:
        yield f"{where} builds a review step"
    if isinstance(node, ast.FunctionDef):
        made_by = "of" if path == STANDING else "standing.of"
        for line in _unfounded(node, made_by):
            yield f"{path}:{line} gives {GUARDED} no standing.of value"


def findings(texts: Mapping[str, str]) -> Sequence[str]:
    """What breaks the rule in the texts of the package.

    Args:
        texts: each file's text, by its path from the repository's root.

    Returns:
        One line for each place that does.
    """
    package = _trees(texts)
    return [
        *(
            each
            for path, tree in package.items()
            for node, inside in _nodes(tree)
            for each in _broken(path, node, inside)
        ),
        *_signature(package.get(STEPS, EMPTY)),
    ]


def _changed(path: str, old: str, new: str) -> Mapping[str, str]:
    return {**TEXTS, path: TEXTS[path].replace(old, new) if old else TEXTS[path] + new}


# each way out of the rule: the file, the text it replaces ("" appends), the new text,
# and what the proof says of it
BREAKS = {
    "a Standing built in flow": (
        FLOW,
        "",
        "\nHAND = steps.Standing(head='a', body='b', stage=None)\n",
        "builds a Standing",
    ),
    "a review step built by hand": (
        FLOW,
        "",
        "\nSTEP = steps.Next(step=steps.Step.REGULAR_REVIEW)\n",
        "builds a review step",
    ),
    "a review step made by replacing": (
        FLOW,
        "",
        "\nSTEP = dataclasses.replace(x, step=steps.Step.REGULAR_REVIEW)\n",
        "builds a review step",
    ),
    "a review step looked up by name": (
        FLOW,
        "",
        "\nSTEP = steps.Step['REGULAR_REVIEW']\n",
        "builds a review step",
    ),
    "a review step from a standing of no origin": (
        FLOW,
        "",
        "\n\ndef _forged(held):\n    return steps.regular_review(held)\n",
        "no standing.of value",
    ),
    "no regular_review at all": (
        STEPS,
        "def regular_review(standing: Standing)",
        "def regular_reviewed(standing: Standing)",
        "no single regular_review",
    ),
    "a regular_review that takes something else": (
        STEPS,
        "def regular_review(standing: Standing)",
        "def regular_review(standing: str)",
        "does not take one",
    ),
}


class TestThePackage(unittest.TestCase):
    """The package as it is."""

    def test_the_package_has_no_review_step_without_a_standing(self) -> None:
        """Every review step is built from a standing that ``standing.of`` made."""
        assert_that(findings(TEXTS), empty())

    def test_a_review_step_is_called_for_somewhere(self) -> None:
        """The proof reads the package, so it has a call to read."""
        calls = [
            node
            for tree in _trees(TEXTS).values()
            for node in ast.walk(tree)
            if _called(node) == GUARDED
        ]
        assert_that(len(calls), equal_to(1))

    def test_each_way_out_of_the_rule_is_found(self) -> None:
        """A review step built outside the rule is refused, whichever way."""
        for name, (path, old, new, said) in BREAKS.items():
            with self.subTest(name):
                found = findings(_changed(path, old, new))
                assert_that(any(said in line for line in found), equal_to(True))
