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
import dataclasses
import functools
import os
import pathlib
import shutil
import tempfile
import unittest
from typing import Callable, Iterable, Iterator, TypeVar

Built = TypeVar("Built")


@dataclasses.dataclass(slots=True, kw_only=True)
class State:
    """Who owns the directories made now.

    Attributes:
        test: the test that is running, None between tests.
        process: whether the directories made now live until the process ends.
        owned: the names of the directories that live until the process ends.
    """

    test: unittest.TestCase | None = None
    process: bool = False
    owned: set[str] = dataclasses.field(default_factory=set)


STATE = State()


def listing() -> frozenset[str]:
    """The names in the temporary directory the tests make theirs in.

    Returns:
        The names; none when the directory is not there.
    """
    place = tempfile.gettempdir()
    return frozenset(os.listdir(place) if os.path.isdir(place) else ())


def fresh(before: Iterable[str], after: Iterable[str]) -> list[str]:
    """The names that appeared and that nothing owned by the process explains.

    Args:
        before: the names before.
        after: the names after.

    Returns:
        The names in ``after`` and not in ``before``, nor owned by the process,
        sorted.
    """
    return sorted(set(after) - set(before) - STATE.owned)


def begin(test: unittest.TestCase) -> None:
    """Say which test is running: its cleanup removes the directories it makes.

    Args:
        test: the test.
    """
    STATE.test = test


def end() -> None:
    """Say that no test is running."""
    STATE.test = None


def directory() -> pathlib.Path:
    """A new temporary directory, removed when its owner is done.

    Returns:
        Its path; the running test's cleanup removes it, or the end of the
        process when the directory is made inside ``process_wide``; with
        neither, it stays.
    """
    path = pathlib.Path(tempfile.mkdtemp())
    if STATE.process:
        STATE.owned.add(path.name)
        atexit.register(shutil.rmtree, path, ignore_errors=True)
    elif STATE.test is not None:
        STATE.test.addCleanup(shutil.rmtree, path, ignore_errors=True)
    return path


@contextlib.contextmanager
def process_wide() -> Iterator[None]:
    """Make the directories of a block live until the process ends.

    Yields:
        Nothing, while the directories made are the process's.
    """
    before = STATE.process
    STATE.process = True
    try:
        yield
    finally:
        STATE.process = before


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
