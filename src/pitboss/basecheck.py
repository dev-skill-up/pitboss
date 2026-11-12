"""A new test that passes on the base proves nothing (pitboss#444, keyword: base-check).

The tests a PR body's Plan rows name must each fail on the base, or pass there
with the body saying why: a line ``Already on main: TEST: REASON``.
"""

import re
from typing import Callable, Mapping, Sequence

from . import plandigest

NAME = re.compile(r"\btest_[a-z0-9_]+\b")
ALREADY = re.compile(r"^Already on main: (test_\w+): (\S.*)$", re.MULTILINE)


def named(body: str, module_of: Callable[[str], str | None]) -> Sequence[str]:
    """The tests the Plan rows of a body name, once each, in order.

    Args:
        body: the PR body.
        module_of: the test module that defines a test name, or None.

    Returns:
        ``module.name`` of each; a word that is no test's name is not one.
    """
    found = dict.fromkeys(NAME.findall(plandigest.section(body)))
    return [f"{module_of(each)}.{each}" for each in found if module_of(each)]


def excused(body: str) -> Sequence[str]:
    """The tests the body lists as already on main, each with a reason.

    Args:
        body: the PR body.

    Returns:
        The test names.
    """
    return [each.group(1) for each in ALREADY.finditer(body)]


def verdict(body: str, tests: Sequence[str], passed: Mapping[str, bool]) -> str:
    """The one line of the check.

    Args:
        body: the PR body.
        tests: the tests the Plan rows name, ``module.name``.
        passed: whether each passed on the base.

    Returns:
        ``base check: ok`` when each test fails on the base or is excused, else
        ``base check: FAILED TEST`` for the first that passes with no reason.
    """
    free = excused(body)
    bad = [t for t in tests if passed.get(t, False) and t.split(".")[1] not in free]
    return f"base check: FAILED {bad[0]}" if bad else "base check: ok"
