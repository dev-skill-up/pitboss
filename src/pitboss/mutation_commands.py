"""The ``mutation-check`` command: do the register's tests notice a broken function.

Keyword: mutation-check. For every enforced or output row of ``rules.tsv`` it
rewrites the row's function with one small mutation at a time, in a copy of the
tree, and runs only that row's named tests; a mutant no test fails is a survivor.
It prints ``mutation: ok`` when there is none. A long run: CI's, not a local one.

A mutant is broken code, and one once replaced a node of ``/dev``. Every run
therefore happens in a private mount namespace where ``/dev`` is read-only
(keyword: mutation-sandbox); when that namespace cannot be made the command
refuses to run anything. Nothing in this module touches ``/dev``.
"""

import argparse
import ast
import concurrent.futures
import importlib.resources
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, mutation, rules

# bind /dev onto itself and remount that bind read-only, inside the namespace only
SCRIPT = 'mount --bind /dev /dev && mount -o remount,bind,ro /dev && exec "$@"'
PROBE = "import os; raise SystemExit(0 if not os.access('/dev', os.W_OK) else 1)"
REFUSED = "mutation-check: refused: no private mount namespace with a read-only /dev"


def sandbox(program: str) -> Sequence[str]:
    """The words that put a command in a namespace where ``/dev`` is read-only.

    Args:
        program: the ``unshare`` program.

    Returns:
        ``unshare -m`` as root, ``unshare -rm`` (a user namespace) otherwise,
        and the shell that makes the bind.
    """
    flags = "-m" if os.geteuid() == 0 else "-rm"
    return [program, flags, "sh", "-c", SCRIPT, "sh"]


def works(prefix: Sequence[str]) -> bool:
    """Whether the sandbox can be made and makes ``/dev`` read-only.

    Args:
        prefix: the words ``sandbox`` gave.

    Returns:
        True when a Python run in it finds ``/dev`` not writable. The probe only
        asks the kernel (``os.access``); it writes nothing.
    """
    try:
        done = subprocess.run(
            [*prefix, sys.executable, "-c", PROBE],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return done.returncode == 0


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
        module, _, name = each.rpartition(".")
        path = tree / "pitboss" / "tests" / f"{module}.py"
        owner = next(
            (
                node.name
                for node in ast.parse(path.read_text(encoding="utf-8")).body
                if isinstance(node, ast.ClassDef)
                and any(
                    isinstance(inner, ast.FunctionDef) and inner.name == name
                    for inner in node.body
                )
            ),
            None,
        )
        ids.append(
            f"pitboss.tests.{module}.{owner}.{name}"
            if owner
            else f"pitboss.tests.{module}"
        )
    return ids


def run_tests(prefix: Sequence[str], tree: pathlib.Path, ids: Sequence[str]) -> bool:
    """Run tests in a tree, in the sandbox.

    Args:
        prefix: the words ``sandbox`` gave.
        tree: the directory that holds the ``pitboss`` package.
        ids: the dotted test names.

    Returns:
        True when they all pass.
    """
    done = subprocess.run(
        [*prefix, sys.executable, "-m", "virtue", *ids],
        cwd=tree,
        env={**os.environ, "PYTHONPATH": str(tree)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return done.returncode == 0


def _killer(
    prefix: Sequence[str], source_tree: pathlib.Path, module: str, ids: Sequence[str]
) -> Callable[[str], bool]:
    def killed(text: str) -> bool:
        with tempfile.TemporaryDirectory() as scratch:
            copy = pathlib.Path(scratch)
            shutil.copytree(source_tree / "pitboss", copy / "pitboss")
            (copy / "pitboss" / f"{module}.py").write_text(text, encoding="utf-8")
            return not run_tests(prefix, copy, ids)

    return killed


def check_row(
    prefix: Sequence[str], source_tree: pathlib.Path, row: rules.Row
) -> Sequence[str]:
    """The findings for one row: a failing control, or each survivor.

    Args:
        prefix: the words ``sandbox`` gave.
        source_tree: the directory that holds the ``pitboss`` package.
        row: the row.

    Returns:
        The findings; none when the tests pass and every mutant is killed.
    """
    module, _, name = row.function.rpartition(".")
    ids = test_ids(source_tree, row.tests)
    if not run_tests(prefix, source_tree, ids):
        return [f"control-failed: {row.id} {row.function}: its tests fail unmutated"]
    path = source_tree / "pitboss" / f"{module}.py"
    return mutation.survivors(
        row.id,
        path.read_text(encoding="utf-8"),
        name,
        _killer(prefix, source_tree, module, ids),
    )


@ENTRY_DATA.register(
    add_argument("rows", nargs="*", help="the rule ids to check (default: all)"),
    add_argument(
        "--source",
        default=None,
        help="the directory that holds the pitboss package (default: the installed"
        " one's)",
    ),
    add_argument(
        "--unshare", default="unshare", help="the program that makes the namespace"
    ),
    add_argument("--jobs", type=int, default=os.cpu_count() or 1, help="rows at once"),
    name="mutation-check",
)
def mutation_check(args: argparse.Namespace) -> None:
    """Mutate the function of each rule and run only that rule's tests.

    Prints a finding for each survivor, and ``mutation: ok`` when there is none.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 when a mutant survives or a control fails; 2 when the
            sandbox cannot be made.
    """
    prefix = sandbox(args.unshare)
    if not works(prefix):
        print(REFUSED)
        raise SystemExit(2)
    package = importlib.resources.files("pitboss")
    tree = (
        pathlib.Path(args.source) if args.source else pathlib.Path(str(package)).parent
    )
    register = (tree / "pitboss" / "rules.tsv").read_text(encoding="utf-8")
    chosen = [
        each
        for each in rules.parse(register)[0]
        if each.kind in rules.CHECKED and (not args.rows or each.id in args.rows)
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        results = list(pool.map(lambda each: check_row(prefix, tree, each), chosen))
    found = [line for lines in results for line in lines]
    for each in found:
        print(each)
    print("mutation: ok" if not found else f"mutation: {len(found)} findings")
    if found:
        raise SystemExit(1)
