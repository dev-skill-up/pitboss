"""Tests for the blocks of Evidence that expand did not produce (pitboss#117)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import evidence, expansion
from .linting import RAN as GENERATED

TYPED = "```\n$ nox -s tests\nOK\n```\n"
FORGED = TYPED.replace("```\n", "```pitboss-expand sha256=0000000000000000\n", 1)
FENCED = expansion.Outcome(status=0, output="```\n$ x\n```\n")
HEADINGS = expansion.Outcome(status=0, output="# Evidence\n## Other\n")
# each text and the opening lines of the blocks refused in it
CASES: Mapping[str, tuple[str, Sequence[int]]] = {
    "a block expand produced": (f"## Evidence\n\n{GENERATED}", []),
    "a fence in the output stays inside": (
        f"## Evidence\n\n{expansion.block('cat f', FENCED)}",
        [],
    ),
    "a typed block": (f"## Evidence\n\n{TYPED}", [3]),
    "an edited block": (f"## Evidence\n\n{GENERATED.replace('OK', 'OKAY')}", [3]),
    "a mark with another digest": (f"## Evidence\n\n{FORGED}", [3]),
    "a command below the first line": ("## Evidence\n\n```\nnote\n$ x\n```\n", [3]),
    "a block with no command": ("## Evidence\n\n```\nOK\n```\n", []),
    "a block never closed": ("## Evidence\n\n```\n$ x\nOK\n", [3]),
    "a produced block never closed": (
        f"## Evidence\n\n{GENERATED.rsplit('```', 1)[0]}",
        [3],
    ),
    "tildes": ("## Evidence\n\n~~~\n$ x\n~~~\n", [3]),
    "typed before Evidence": (f"## Plan\n\n{TYPED}\n## Evidence\n\n{GENERATED}", []),
    "typed after Evidence": (f"## Evidence\n\n{GENERATED}\n## Notes\n\n{TYPED}", []),
    "a deeper heading stays inside": (f"## Evidence\n\n### Run\n\n{TYPED}", [5]),
    "a same level heading ends it": (
        f"### Evidence\n\n{GENERATED}### Run\n\n{TYPED}",
        [],
    ),
    "a bare deeper heading stays inside": (f"## Evidence\n\n###\n\n{TYPED}", [5]),
    "a bare top heading ends it": (f"## Evidence\n\n#\n\n{TYPED}", []),
    "a heading in the output": (
        f"## Evidence\n\n{expansion.block('cat f', HEADINGS)}\n{TYPED}",
        [9],
    ),
}


class TestHandTyped(unittest.TestCase):
    """Which blocks of a body are refused."""

    def test_each_case(self) -> None:
        """A block with a command line is refused unless expand produced it."""
        for name, (text, refused) in CASES.items():
            with self.subTest(name):
                assert_that(evidence.hand_typed(text), equal_to(refused))
