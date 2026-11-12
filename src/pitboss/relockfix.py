"""A relock whose diff has a test file beside the pins shows the data behind it.

Pitboss#447.

(Keyword: relock-test-fix.) The Opus ruling of 2026-11-10 on quire PR 1101: the
review was changes needed for a missing section, and the comment quoted 3.6 to
6.7 pages while the body's table showed 2.61 to 6.90 (ruling 2026-11-10T20:11Z).
A hand-back for such a relock needs a section of the body that names the test
file and why, with each run as a link and the maximum and the margin, and every
range the ``Test fix`` comment quotes is the minimum and the maximum of the
table's last column.
"""

import re
from typing import Sequence

from .textparts import section_after

RELOCK_PREFIX = "relock/"
TEST_PATH = re.compile(
    r"(?:^|/)(?:tests?/|test_[^/]*$|[^/]*_test\.[^/]*$|[^/]*\.spec\.)"
)
HEADING = re.compile(r"(?im)^#+[ \t]*test fix\b.*$")
RUN_LINK = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/actions/runs/\d+")
RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(\d+(?:\.\d+)?)")
CELL = re.compile(r"^\|(?:[^|\n]*\|)*?\s*(-?\d+(?:\.\d+)?)\s*\|\s*$", re.M)


def test_files(names: Sequence[str]) -> Sequence[str]:
    """The changed paths that are test files.

    Args:
        names: the paths a PR changes.

    Returns:
        The paths of tests.
    """
    return [each for each in names if TEST_PATH.search(each)]


NEXT_HEADING = re.compile(r"(?m)^#{1,6}[ \t]")


def _section(body: str) -> str:
    found = HEADING.search(body)
    if found is None:
        return ""
    return found.group(0) + section_after(body, found, NEXT_HEADING)


def _column(section: str) -> Sequence[float]:
    return [float(each) for each in CELL.findall(section)]


def findings(body: str, comment: str, names: Sequence[str]) -> Sequence[str]:
    """What a relock hand-back lacks when its diff has a test file beside the pins.

    Args:
        body: the PR's body.
        comment: the text of the PR's ``Test fix`` comment, empty when it has none.
        names: the paths the PR changes.

    Returns:
        A refusal for each thing missing; none when the diff has no test file.
    """
    tests = test_files(names)
    if not tests:
        return []
    section = _section(body)
    found = [
        f"refused: the relock body lacks {why} (relock-test-fix)"
        for why in _missing(section, tests[0])
    ]
    return [*found, *_figures(section, comment)]


def _missing(section: str, test: str) -> Sequence[str]:
    # what the Test fix section lacks, of the first test file's
    return [
        why
        for why, absent in (
            ("a `Test fix` section", not section),
            (f"the test file {test}", test not in section),
            ("each run as a link", not RUN_LINK.search(section)),
            ("the maximum and the margin", not re.search(r"(?i)maximum", section)),
        )
        if absent
    ]


def _figures(section: str, comment: str) -> Sequence[str]:
    column = _column(section)
    if not column:
        return []
    low, high = min(column), max(column)
    return [
        f"refused: the test-fix comment quotes {a} to {b}, but the body's table"
        f" has {low:g} to {high:g} (relock-test-fix)"
        for a, b in RANGE.findall(comment)
        if (float(a), float(b)) != (low, high)
    ]
