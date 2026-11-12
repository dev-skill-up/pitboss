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

from . import rules_commands

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
    module, _, name = test.rpartition(".")
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
    module, _, name = test.rpartition(".")
    text = rules_commands.module_text(module)
    return text is not None and re.search(rf"def {re.escape(name)}\(", text) is not None


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


@contextlib.contextmanager
def base_source(repo: pathlib.Path, ref: str) -> Iterator[pathlib.Path]:
    """The ``src`` of a scratch worktree of the base, with the head's tests in it.

    Args:
        repo: a checkout of pitboss.
        ref: the base.

    Yields:
        The directory that holds the base's ``pitboss`` package.
    """
    git = ["git", "-C", str(repo)]
    with tempfile.TemporaryDirectory(prefix="done-when-") as scratch:
        tree = pathlib.Path(scratch) / "tree"
        subprocess.run(
            [*git, "worktree", "add", "--detach", str(tree), ref],
            check=True,
            capture_output=True,
        )
        try:
            shutil.copytree(
                pathlib.Path(str(importlib.resources.files("pitboss") / "tests")),
                tree / "src" / "pitboss" / "tests",
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            yield tree / "src"
        finally:
            subprocess.run(
                [*git, "worktree", "remove", "--force", str(tree)],
                check=True,
                capture_output=True,
            )
