"""Temporary directories of the tests, and who removes them (pitboss#346).

The tests session gives the tests a ``TMPDIR`` that a green run empties and a
green run with something left in it fails (keyword: test-leak). A test makes its
directories with ``directory``, which registers their removal with the test that
is running, or removes them in its own cleanup. A directory built once for the
whole run (a template that each test copies) belongs to the process, and is
removed when the process ends. This module imports nothing of pitboss.
"""

import atexit
import contextlib
import contextvars
import functools
import os
import pathlib
import shutil
import tempfile
import unittest
from typing import (
    AbstractSet,
    Callable,
    Iterable,
    Iterator,
    MutableSet,
    Sequence,
    TypeVar,
)

Built = TypeVar("Built")

# the test that is running, None between tests
TEST: contextvars.ContextVar[unittest.TestCase | None] = contextvars.ContextVar(
    "test", default=None
)
# whether the directories made now live until the process ends
PROCESS: contextvars.ContextVar[bool] = contextvars.ContextVar("process", default=False)
# the names of the directories that live until the process ends
OWNED: MutableSet[str] = set()


def listing() -> AbstractSet[str]:
    """The names in the temporary directory the tests make theirs in.

    Returns:
        The names; none when the directory is not there.
    """
    place = tempfile.gettempdir()
    return frozenset(os.listdir(place) if os.path.isdir(place) else ())


def fresh(before: Iterable[str], after: Iterable[str]) -> Sequence[str]:
    """The names that appeared and that nothing owned by the process explains.

    Args:
        before: the names before.
        after: the names after.

    Returns:
        The names in ``after`` and not in ``before``, nor owned by the process,
        sorted.
    """
    return sorted(set(after) - set(before) - OWNED)


def begin(test: unittest.TestCase) -> None:
    """Say which test is running: its cleanup removes the directories it makes.

    Args:
        test: the test.
    """
    TEST.set(test)


def end() -> None:
    """Say that no test is running."""
    TEST.set(None)


def directory() -> pathlib.Path:
    """A new temporary directory, removed when its owner is done.

    Returns:
        Its path; the running test's cleanup removes it, or the end of the
        process when the directory is made inside ``process_wide``; with
        neither, it stays.
    """
    path = pathlib.Path(tempfile.mkdtemp())
    own(path)
    return path


def own(path: pathlib.Path) -> None:
    """Remove a path, made by hand in the temporary directory, when its owner is done.

    Args:
        path: the path; inside ``process_wide`` the process removes it when it
            ends, else the running test's cleanup does, and when no test is
            running it stays.
    """
    running = TEST.get()
    if PROCESS.get():
        OWNED.add(path.name)
        atexit.register(shutil.rmtree, path, ignore_errors=True)
    elif running is not None:
        running.addCleanup(shutil.rmtree, path, ignore_errors=True)


@contextlib.contextmanager
def process_wide() -> Iterator[None]:
    """Make the directories of a block live until the process ends.

    Yields:
        Nothing, while the directories made are the process's.
    """
    token = PROCESS.set(True)
    try:
        yield
    finally:
        PROCESS.reset(token)


def process_directory() -> pathlib.Path:
    """A new temporary directory that lives until the process ends.

    Returns:
        Its path.
    """
    with process_wide():
        return directory()


def built_once(make: Callable[[], Built]) -> Callable[[], Built]:
    """A world built by the first test that asks and never again.

    Args:
        make: builds it.

    Returns:
        The function that gives it; its directories are the process's, since
        the test that asks first is not the only one that copies from them.
    """

    def build() -> Built:
        with process_wide():
            return make()

    return functools.cache(build)
