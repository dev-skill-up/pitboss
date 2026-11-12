"""A changed lint, check or exemption with no new test the Plan cites (pitboss#398).

(Keyword: lint-test.) The worker brief's ``Lint tests`` rule says a lint, check
or exemption that is new or loosened ships a test for the nearest input it must
still reject. ``plan-check`` refuses before review a diff that changes a
function of a module that emits findings (a module with a function whose name
has ``finding`` in it) when the diff adds no ``def test_...`` to a test module
that imports the module, cited in the Plan. This is a heuristic: it catches a
missing test, not a wrong one, and a change to a line outside every function
(a constant) is not seen. The module reads no file and calls nothing; it is
given the head's files.
"""

import ast
import re
from typing import Mapping, Sequence

from . import importgraph, markuplines

CHECK = "lint-test"
EMITS = "finding"
CITED = re.compile(r"(?<![A-Za-z0-9_])test_[A-Za-z0-9_]+(?![A-Za-z0-9_])")
ADDED_TEST = re.compile(r"^\+[ \t]*(?:async[ \t]+)?def[ \t]+(test_\w+)", re.MULTILINE)
MISSING = (
    "{check}: `{module}` function `{function}` (`{path}` line {line}) changed and"
    " the diff adds no test that the Plan cites to a test module that imports"
    " it: add a test for the nearest input it must still reject, and cite its"
    " name in a Plan row"
)
Function = ast.FunctionDef | ast.AsyncFunctionDef
Changed = Sequence[tuple[int, bool]]


def _code(row: str) -> bool:
    text = row[1:].strip()
    return bool(text) and not text.startswith("#")


def changed_lines(start: int, rows: str) -> Changed:
    """The code rows of a hunk.

    Args:
        start: the line of the new file where the hunk starts.
        rows: the hunk's rows.

    Returns:
        (line of the new file, whether a docstring there is no change) of each
        row that is code.
    """
    # (line of the new file, whether a docstring there is no change) of each row
    # of a hunk that is code; a removed row stands at the line it was cut after,
    # and a row of a hunk that adds nothing is a deletion, which a docstring keeps
    each = [row for row in rows.split("\n") if row.startswith(("+", "-"))]
    in_place = any(row.startswith("+") for row in each)
    at = [
        start + sum(prior.startswith("+") for prior in each[:i])
        for i in range(len(each))
    ]
    return [(line, in_place) for line, row in zip(at, each) if _code(row)]


def _docstring(node: Function) -> range:
    first = node.body[0]
    value = first.value if isinstance(first, ast.Expr) else None
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return range(first.lineno, (first.end_lineno or first.lineno) + 1)
    return range(0)


def _functions(syntax: ast.AST) -> Sequence[Function]:
    return [each for each in ast.walk(syntax) if isinstance(each, Function)]


def _touched(node: Function, changed: Changed) -> int:
    # the first changed line inside the function, 0 when none
    doc = _docstring(node)
    inside = [
        line
        for line, in_place in changed
        if node.lineno <= line <= (node.end_lineno or node.lineno)
        and not (in_place and line in doc)
    ]
    return min(inside, default=0)


def _changed_in(text: str, changed: Changed) -> Mapping[str, int]:
    # the first changed line of each function of a module that emits findings
    try:
        named = _functions(ast.parse(text))
    except SyntaxError:
        return {}
    if not any(EMITS in each.name for each in named):
        return {}
    lines = [(each.name, _touched(each, changed)) for each in reversed(named)]
    return dict(item for item in lines if item[1])


def _by_path(diff: str) -> Mapping[str, Changed]:
    found: dict[str, list[tuple[int, bool]]] = {}
    for file, start, rows in markuplines.hunks(diff):
        found.setdefault(file, []).extend(changed_lines(start, rows))
    return found


def _tests_of(graph: importgraph.Graph, file: str) -> Sequence[str]:
    # the files of the test modules that import the module of a file
    module = importgraph.module_of(file)
    return [
        "src/" + name.replace(".", "/") + ".py"
        for name, imported in graph.edges.items()
        if importgraph.is_test(name) and module in imported
    ]


def _added(diff: str, files: Sequence[str]) -> set[str]:
    # the names of the tests the diff adds to these files
    return {
        name
        for file, _, rows in markuplines.hunks(diff)
        if file in files
        for name in ADDED_TEST.findall(rows)
    }


def _library(path: str, head: Mapping[str, str]) -> bool:
    module = importgraph.module_of(path)
    return path in head and bool(module) and not importgraph.in_tests(module)


def _message(file: str, name: str, line: int) -> str:
    return MISSING.format(
        check=CHECK,
        module=importgraph.module_of(file),
        function=name,
        path=file,
        line=line,
    )


def _emitted(diff: str, head: Mapping[str, str]) -> Sequence[tuple[str, str, int]]:
    # (file, function, first changed line) of each changed function of a module
    # that emits findings
    return [
        (path, name, line)
        for path, changed in _by_path(diff).items()
        if _library(path, head)
        for name, line in _changed_in(head[path], changed).items()
    ]


def findings(section: str, patch: str, head: Mapping[str, str]) -> Sequence[str]:
    """The changed functions of finding-emitting modules with no cited new test.

    Args:
        section: the Plan section.
        patch: the output of ``git diff -U0 --no-renames`` of the PR.
        head: the text of each ``.py`` file of ``src/pitboss`` at the head, by
            path from the root of the repository (``selectdiff.sources_of``).

    Returns:
        A finding for each function of a module of the package that emits
        findings, whose lines the diff changes (a blank line, a comment and a
        docstring do not count), when no test the diff adds to a test module
        that imports the module is cited in the Plan; none for a test module
        or a file the package does not have.
    """
    emitted = _emitted(patch, head)
    graph = importgraph.build_graph(head) if emitted else None
    cited = set(CITED.findall(section))
    return [
        _message(*each)
        for each in emitted
        if graph and not _added(patch, _tests_of(graph, each[0])) & cited
    ]
