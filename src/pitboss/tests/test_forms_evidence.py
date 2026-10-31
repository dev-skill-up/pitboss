"""Which blocks of a PR body satisfy the evidence checks (pitboss#117)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .formchecks import body_checks, findings
from .linting import BODY, RAN

TYPED = "```\n$ nox -s tests\nOK\n```\n"


def headed(heading: str) -> str:
    """The good body with another heading for its Evidence.

    Args:
        heading: the heading line.

    Returns:
        The body.
    """
    return BODY.replace("## Evidence", heading)


ELSEWHERE = headed("## Plan") + "\n## Evidence\n\nSee.\n"
# each body and the checks it fails
CASES: Mapping[str, tuple[str, Sequence[str]]] = {
    "no space after the hash": (headed("#Evidence"), ["evidence"]),
    "seven hashes": (headed("####### Evidence"), ["evidence"]),
    "a produced block under Plan": (ELSEWHERE, ["evidence"]),
    "a typed block under Plan": (
        ELSEWHERE.replace(RAN, TYPED),
        ["evidence", "hand-typed"],
    ),
    "a typed block under a bare heading": (
        BODY.replace("## Evidence\n\n" + RAN, "#Evidence\n" + TYPED),
        ["evidence", "hand-typed"],
    ),
}


class TestEvidenceSection(unittest.TestCase):
    """The section of Evidence and the rows expand did not produce."""

    def test_one_definition_of_the_section(self) -> None:
        """The heading is the one hand-typed uses, and the block is under it."""
        for name, (text, failed) in CASES.items():
            with self.subTest(name):
                assert_that(body_checks(text), equal_to(failed))

    def test_each_row_is_named(self) -> None:
        """A finding names the line of a row, one for each row."""
        typed = BODY.replace(RAN, "> ```\n> $ nox -s tests\n> $ true\n> ```\n")
        refusal = " row that pitboss expand did not produce: put the command in"
        refusal += " a template and run pitboss expand (hand-typed)"
        assert_that(
            list(findings(typed)[-2:]),
            equal_to([f'text: line {n}: a "$ "{refusal}' for n in (8, 9)]),
        )
