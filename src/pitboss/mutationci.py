"""The mutation check, a step of CI's ``mutation`` job only (keyword: no-local-mutants).

For every enforced or output row of ``rules.tsv`` it rewrites the row's function
with one small mutation at a time, in a copy of the tree, and runs only that row's
named tests and the tests of ``test_mutation_rows`` named for it; a mutant no test
fails is a survivor. A mutant is broken code, and one
run on a host as root once replaced the null device, so this is no pitboss command:
``python -m pitboss.mutationci`` refuses unless ``GITHUB_ACTIONS`` is ``true``, the
ephemeral runner of CI's job (``.github/workflows/mutation.yml``). It has no
local mode and no flag that lifts the refusal.
"""

import ast
import concurrent.futures
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Mapping, Sequence

from . import mutation, rules
from .textparts import split_last

REFUSED = (
    "mutation: refused: mutants run only in CI's mutation job (GITHUB_ACTIONS=true)"
)
Runner = Callable[[pathlib.Path, Sequence[str]], bool]
ROWS = "test_mutation_rows"


def _owner(path: pathlib.Path, name: str) -> str | None:
    body = ast.parse(path.read_text(encoding="utf-8")).body
    for node in body:
        if isinstance(node, ast.ClassDef):
            if any(
                isinstance(inner, ast.FunctionDef) and inner.name == name
                for inner in node.body
            ):
                return node.name
    return None


def test_ids(tree: pathlib.Path, names: Sequence[str]) -> Sequence[str]:
    """The dotted names of a row's tests, with their classes.

    Args:
        tree: the directory that holds the ``pitboss`` package.
        names: ``test_module.test_name`` of each test.

    Returns:
        ``pitboss.tests.test_module.Class.test_name``; a test with no class in the
        module is given as its module alone.
    """
    ids = []
    for each in names:
        module, test = split_last(each, ".")
        owner = _owner(tree / "pitboss" / "tests" / f"{module}.py", test)
        ids.append(
            f"pitboss.tests.{module}.{owner}.{test}"
            if owner
            else f"pitboss.tests.{module}"
        )
    return ids


def killers(tree: pathlib.Path, row: rules.Row) -> Sequence[str]:
    """The tests of ``test_mutation_rows`` that hold a row's function.

    Named by its id and function.

    Args:
        tree: the directory that holds the ``pitboss`` package.
        row: the row.

    Returns:
        Their dotted names.
    """
    prefix = f"test_{row.id.lower()}_{row.function.rpartition('.')[2]}_"
    body = ast.parse(
        (tree / "pitboss" / "tests" / f"{ROWS}.py").read_text(encoding="utf-8")
    ).body
    names = [
        inner.name
        for node in body
        if isinstance(node, ast.ClassDef)
        for inner in node.body
        if isinstance(inner, ast.FunctionDef)
    ]
    return test_ids(
        tree, [f"{ROWS}.{name}" for name in names if name.startswith(prefix)]
    )


def virtue(tree: pathlib.Path, ids: Sequence[str]) -> bool:  # pragma: no cover
    """Run tests in a tree (CI's runner only: no test runs a mutant here).

    Args:
        tree: the directory that holds the ``pitboss`` package.
        ids: the dotted test names.

    Returns:
        True when they all pass.
    """
    done = subprocess.run(
        [sys.executable, "-m", "virtue", *ids],
        cwd=tree,
        env={**os.environ, "PYTHONPATH": str(tree)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return done.returncode == 0


def _killer(
    runner: Runner, source: pathlib.Path, module: str, ids: Sequence[str]
) -> Callable[[str], bool]:
    def killed(text: str) -> bool:
        with tempfile.TemporaryDirectory() as scratch:
            copy = pathlib.Path(scratch)
            shutil.copytree(source / "pitboss", copy / "pitboss")
            (copy / "pitboss" / f"{module}.py").write_text(text, encoding="utf-8")
            return not runner(copy, ids)

    return killed


def check_row(runner: Runner, source: pathlib.Path, row: rules.Row) -> Sequence[str]:
    """The findings for one row: a failing control, or each survivor.

    Args:
        runner: what runs a tree's tests.
        source: the directory that holds the ``pitboss`` package.
        row: the row.

    Returns:
        The findings; none when the tests pass and every mutant is killed.
    """
    module, _, name = row.function.rpartition(".")
    ids = [*test_ids(source, row.tests), *killers(source, row)]
    if not runner(source, ids):
        return [f"control-failed: {row.id} {row.function}: its tests fail unmutated"]
    text = (source / "pitboss" / f"{module}.py").read_text(encoding="utf-8")
    return mutation.survivors(row.id, text, name, _killer(runner, source, module, ids))


def _chosen(source: pathlib.Path, argv: Sequence[str]) -> Sequence[rules.Row]:
    # the checked rows of the register, those named when any are
    table = source / "pitboss" / "rules.tsv"
    register = rules.parse(table.read_text(encoding="utf-8"))[0]
    return [
        each
        for each in register
        if each.kind in rules.CHECKED and (not argv or each.id in argv)
    ]


def _checked(
    runner: Runner, source: pathlib.Path, chosen: Sequence[rules.Row]
) -> Sequence[str]:
    # every row's findings, the rows checked side by side
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 1) as pool:
        said = pool.map(lambda each: check_row(runner, source, each), chosen)
        return [finding for row in said for finding in row]


def main(
    argv: Sequence[str],
    environ: Mapping[str, str],
    runner: Runner,
    source: pathlib.Path,
) -> int:
    """Check the rows named (all when none), in CI only.

    Args:
        argv: the rule ids.
        environ: the environment.
        runner: what runs a tree's tests.
        source: the directory that holds the ``pitboss`` package.

    Returns:
        0 when no mutant survives, 1 when one does or a control fails, 2 outside CI.
    """
    if environ.get("GITHUB_ACTIONS") != "true":
        print(REFUSED)
        return 2
    found = _checked(runner, source, _chosen(source, argv))
    for each in found:
        print(each)
    print("mutation: ok" if not found else f"mutation: {len(found)} findings")
    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(
        main(sys.argv[1:], os.environ, virtue, pathlib.Path(__file__).parent.parent)
    )
