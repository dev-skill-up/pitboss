"""Run the Done-when's tests on the head and on a base (pitboss#444, done-when-check).

The tests of the head are copied over a scratch worktree of the base, so a test of
behaviour the base lacks fails there by its own assertion or its import.
"""

import concurrent.futures
import contextlib
import importlib.resources
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Iterator, Mapping, Sequence

from . import donewhencheck, rules, rules_commands

WORKERS = 8
# The commands register themselves on import; a test run alone needs all of them.
PROGRAM = """
import importlib, pkgutil, sys, unittest, pitboss
for each in pkgutil.iter_modules(pitboss.__path__):
    if each.name.endswith("_commands"):
        importlib.import_module("pitboss." + each.name)
unittest.main(module=sys.argv[1], argv=["unittest", "-k", sys.argv[2]])
"""


def passes(test: str, source: pathlib.Path) -> bool:
    """Whether one test passes when pitboss is read from a source directory.

    Args:
        test: ``test_module.test_name``.
        source: the directory that holds the ``pitboss`` package.

    Returns:
        True when unittest exits 0.
    """
    module, name = test.split(".")
    done = subprocess.run(
        [sys.executable, "-c", PROGRAM, f"pitboss.tests.{module}", name],
        env={**os.environ, "PYTHONPATH": str(source)},
        capture_output=True,
        check=False,
    )
    return done.returncode == 0


def exists(test: str) -> bool:
    """Whether a test is defined in a test module of pitboss.

    Args:
        test: ``test_module.test_name``.

    Returns:
        True when the module has a ``def`` of that name.
    """
    module, name = test.split(".")
    body = rules_commands.module_text(module)
    return body is not None and re.search(rf"def {re.escape(name)}\(", body) is not None


def run_all(tests: Sequence[str], source: pathlib.Path) -> Mapping[str, bool]:
    """Run tests side by side.

    Args:
        tests: the tests.
        source: the directory that holds the ``pitboss`` package.

    Returns:
        Whether each passed.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        got = pool.map(lambda each: passes(each, source), tests)
    return dict(zip(tests, got))


def install_tests(tree: pathlib.Path) -> None:
    """Copy the head's tests over a worktree of the base.

    Args:
        tree: the worktree.
    """
    heads = importlib.resources.files("pitboss") / "tests"
    shutil.copytree(
        pathlib.Path(str(heads)),
        tree / "src" / "pitboss" / "tests",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__"),
    )


def git(repo: pathlib.Path, *words: str) -> None:
    """Run git in a checkout, saying nothing.

    Args:
        repo: the checkout.
        *words: the arguments.
    """
    subprocess.run(["git", "-C", str(repo), *words], check=True, capture_output=True)


@contextlib.contextmanager
def base_source(repo: pathlib.Path, ref: str) -> Iterator[pathlib.Path]:
    """The ``src`` of a scratch worktree of the base, with the head's tests in it.

    Args:
        repo: a checkout of pitboss.
        ref: the base.

    Yields:
        The directory that holds the base's ``pitboss`` package.
    """
    with tempfile.TemporaryDirectory(prefix="done-when-") as scratch:
        tree = pathlib.Path(scratch) / "tree"
        git(repo, "worktree", "add", "--detach", str(tree), ref)
        try:
            install_tests(tree)
            yield tree / "src"
        finally:
            git(repo, "worktree", "remove", "--force", str(tree))


def measure(
    items: Sequence[donewhencheck.Item],
    rows: Sequence[rules.Row],
    base: tuple[pathlib.Path, str],
) -> donewhencheck.Checks:
    """Run the tests the items name on the head and on the base.

    Args:
        items: the items.
        rows: the register's rows.
        base: a checkout of pitboss and the ref of the base in it.

    Returns:
        What is known of the tests.
    """
    named = {t for each in items for t in donewhencheck.tests_of(each, rows)}
    tests = sorted(each for each in named if "." in each)
    head_src = pathlib.Path(str(importlib.resources.files("pitboss"))).parent
    with base_source(*base) as base_src:
        return donewhencheck.Checks(
            exists=exists, head=run_all(tests, head_src), base=run_all(tests, base_src)
        )
