"""An Impact row cites one disposition for each of its hits (pitboss#317)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import impact, impactcount, plancheck
from .test_plan_check_remote import mentions


def hits(path: str, lines: Sequence[int]) -> Sequence[impact.Hit]:
    """Hits of a file.

    Args:
        path: the file.
        lines: the lines.

    Returns:
        A hit at each.
    """
    return [impact.Hit(path=path, line=n, text="x") for n in lines]


# the hits of each phrase of the fake tree
HITS: Mapping[str, Sequence[impact.Hit]] = {
    "alpha": hits("a.py", [1, 2, 3, 4]),
    "beta": hits("b.py", [1, 2]),
    "both": [*hits("a.py", [1, 2]), *hits("b.py", [1])],
}
HEAD = "## Plan\n1. `pitboss impact alpha`\n"


def disposed(path: str, lines: Sequence[int]) -> str:
    """Disposition lines of a file.

    Args:
        path: the file.
        lines: the lines it has hits at.

    Returns:
        The lines, one each.
    """
    return "".join(f"- {path}:{n}: edited\n" for n in lines)


def search(phrases: Sequence[str]) -> Sequence[impact.Hit]:
    """The hits of the fake tree.

    Args:
        phrases: the phrases.

    Returns:
        Their hits.
    """
    return HITS[phrases[0]]


def shared(note: str) -> str:
    """A Plan whose rows share hits, cited under the first.

    Args:
        note: what the second row says after its command.

    Returns:
        The Plan section.
    """
    return (
        "## Plan\n1. `pitboss impact both`\n"
        + disposed("a.py", [1, 2])
        + disposed("b.py", [1])
        + f"2. `pitboss impact alpha`{note}\n"
        + disposed("a.py", [3, 4])
    )


# each case: the Plan section, and the words of each finding expected
CASES: Mapping[str, tuple[str, Sequence[Sequence[str]]]] = {
    "four hits and three dispositions": (
        HEAD + disposed("a.py", [1, 2, 3]),
        [["impact-count:", "row 1 has 4 hits", "cites 3 distinct"]],
    ),
    "four hits and four dispositions": (HEAD + disposed("a.py", [1, 2, 3, 4]), []),
    "a hit cited twice is cited once": (
        HEAD + disposed("a.py", [1, 2, 3, 3]),
        [["row 1 has 4 hits", "cites 3 distinct"]],
    ),
    "dispositions under each of two rows": (
        HEAD
        + disposed("a.py", [1, 2, 3, 4])
        + "2. `pitboss impact beta`\n"
        + disposed("b.py", [1, 2]),
        [],
    ),
    "a hit cited under the row of another command": (
        HEAD
        + "2. `pitboss impact beta`\n"
        + disposed("a.py", [1])
        + disposed("b.py", [1, 2]),
        [
            ["row 1 has 4 hits", "cites 0"],
            ["row 2 has 2 hits", "cites 3"],
            ["row 2 cites a.py:1", "another row"],
        ],
    ),
    "shared hits cited under the first row and said so in the second": (
        shared("; the hits of row 1 are cited under row 1"),
        [],
    ),
    "shared hits cited once and not said so": (
        shared(""),
        [["row 2 has 4 hits", "cites 2"]],
    ),
    "a command with a dollar": (
        "## Plan\n$ pitboss impact alpha\n" + disposed("a.py", [1, 2]),
        [["row 1 has 4 hits", "cites 2"]],
    ),
    "a row that is no impact command": (
        "## Plan\n1. `rg x`\n" + disposed("zz.py", [1]),
        [],
    ),
}


class TestCount(unittest.TestCase):
    """The hits of a row and its dispositions."""

    def test_each_case(self) -> None:
        """Done-when: 4 hits and 3 dispositions are refused, 4 and 4 pass."""
        for name, (section, words) in CASES.items():
            with self.subTest(name):
                found = impactcount.findings(section, search)
                assert_that(mentions(found, words), equal_to(True))

    def test_the_commands_of_a_plan_are_found_once(self) -> None:
        """The `$` lines and the spans of the rows, each list of phrases once."""
        section = (
            "## Plan\n1. `pitboss impact alpha` and `rg x`\n$ pitboss impact alpha\n"
        )
        assert_that(impactcount.phrases(section), equal_to([("alpha",)]))

    def test_plan_check_reports_the_count(self) -> None:
        """The findings are counted in the verdict."""
        found = impactcount.findings(HEAD, search)
        assert_that(
            plancheck.verdict([], found),
            equal_to("Plan check: refused, Impact count findings: 1"),
        )
