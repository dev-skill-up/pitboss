"""Tests for the rows of a body that expand did not produce (pitboss#117)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import evidence, expansion
from .linting import RAN as GENERATED

TYPED = "```\n$ nox -s tests\nOK\n```\n"
FORGED = TYPED.replace("```\n", "```pitboss-expand sha256=0000000000000000\n", 1)
FENCED = expansion.Outcome(status=0, output="```\n$ x\n```\n")
HEADINGS = expansion.Outcome(status=0, output="# Evidence\n## Other\n")
# a block that expand made for "$ true", then lines typed to look like output
TRUE = "$ true\n"
OPENING = f"```{expansion.info(TRUE)}\n"
# each text and the numbers of the lines refused in it
CASES: Mapping[str, tuple[str, Sequence[int]]] = {
    "a block expand produced": (f"## Evidence\n\n{GENERATED}", []),
    "a fence in the output stays inside": (
        f"## Evidence\n\n{expansion.block('cat f', FENCED)}",
        [],
    ),
    "a typed block": (f"## Evidence\n\n{TYPED}", [4]),
    "an edited block": (f"## Evidence\n\n{GENERATED.replace('OK', 'OKAY')}", [4]),
    "a mark with another digest": (f"## Evidence\n\n{FORGED}", [4]),
    "a command below the first line": ("## Evidence\n\n```\nnote\n$ x\n```\n", [5]),
    "a block with no command": ("## Evidence\n\n```\nOK\n```\n", []),
    "a block never closed": ("## Evidence\n\n```\n$ x\nOK\n", [4]),
    "a produced block never closed": (
        f"## Evidence\n\n{GENERATED.rsplit('```', 1)[0]}",
        [4],
    ),
    "tildes": ("## Evidence\n\n~~~\n$ x\n~~~\n", [4]),
    "a dollar sign in prose": ("## Evidence\n\n$HOME costs $5\n", []),
    "a produced block in the plan": (f"## Plan\n\n{GENERATED}", []),
    "a closing fence of three spaces": (
        f"## Evidence\n\n{OPENING}$ true\n   ```\n",
        [],
    ),
    "a closing fence of four spaces does not close": (
        f"## Evidence\n\n{OPENING}$ true\n    ```\n$ nox -s tests\nOK\n```\n",
        [4, 6],
    ),
    "a closing fence after a tab does not close": (
        f"## Evidence\n\n{OPENING}$ true\n\t```\n$ nox -s tests\nOK\n```\n",
        [4, 6],
    ),
    "a closing fence with words does not close": (
        f"## Evidence\n\n{OPENING}$ true\n``` x\n$ nox -s tests\n```\n",
        [4, 6],
    ),
    "a shorter closing fence does not close": (
        "## Evidence\n\n````\n$ x\n```\n$ y\n````\n",
        [4, 6],
    ),
    "a longer closing fence closes": (f"## Evidence\n\n{OPENING}$ true\n````\n", []),
    "a typed block in a quote": (
        "## Evidence\n\n> ```\n> $ nox -s tests\n> OK\n> ```\n",
        [4],
    ),
    "a typed block in a quote without a space": ("> ```\n>$ x\n> ```\n", [2]),
    "a typed block in a bullet": (
        "## Evidence\n\n- ```\n  $ nox -s tests\n  ```\n",
        [4],
    ),
    "a typed block in a plus item": ("+ ```\n  $ x\n  ```\n", [2]),
    "a typed block in a star item": ("* ```\n  $ x\n  ```\n", [2]),
    "a typed block in a numbered item": ("1. ```\n   $ x\n   ```\n", [2]),
    "a typed block in a bracket item": ("10) ```\n    $ x\n    ```\n", [2]),
    "a row on a list marker": ("- $ x\n", [1]),
    "a row in a nested quote and list": ("> - > $ x\n", [1]),
    "an indented row in a fence": (
        "## Evidence\n\n```\n $ nox -s tests\nOK\n```\n",
        [4],
    ),
    "a row after a tab": ("## Evidence\n\n```\n$\tnox -s tests\nOK\n```\n", [4]),
    "a row of only a dollar": ("## Evidence\n\n```\n$\nOK\n```\n", [4]),
    "a row in a code block": (
        "## Evidence\n\ntext\n\n    $ nox -s tests\n    OK\n",
        [5],
    ),
    "a row after a tab indent": ("## Evidence\n\n\t$ nox -s tests\n", [3]),
    "a row with carriage returns": ("```\r\n$ x\r\n```\r\n", [2]),
    "a heading Evidence hidden from lint": (
        "Evidence\n========\n\n```\n$ nox -s tests\nOK\n```\n",
        [5],
    ),
    "typed before Evidence": (f"## Plan\n\n{TYPED}\n## Evidence\n\n{GENERATED}", [4]),
    "typed after Evidence": (f"## Evidence\n\n{GENERATED}\n## Notes\n\n{TYPED}", [11]),
    "typed under a heading of another section": (f"## Execution\n\n{TYPED}", [4]),
    "a pre block with an entity dollar": (
        "## Evidence\n\n<pre>\n&#36; nox -s tests\nOK\n</pre>\n",
        [4],
    ),
    "a pre tag on the row": ("## Evidence\n\n<pre>$ nox -s tests\nOK\n</pre>\n", [3]),
    "a no-break space after the dollar": (
        "## Evidence\n\n```\n$\u00a0nox -s tests\nOK\n```\n",
        [4],
    ),
    "a zero-width space before the dollar": (
        "## Evidence\n\n```\n\u200b$ nox -s tests\nOK\n```\n",
        [4],
    ),
    "a byte order mark before the dollar": (
        "## Evidence\n\n```\n\ufeff$ nox -s tests\nOK\n```\n",
        [4],
    ),
    "a no-break space before the dollar": (
        "## Evidence\n\n```\n\u00a0$ nox -s tests\nOK\n```\n",
        [4],
    ),
    "a fullwidth dollar": (
        "## Evidence\n\n```\n\uff04 nox -s tests\nOK\n```\n",
        [4],
    ),
    "a no-break space in produced output": (
        "## Evidence\n\n"
        + expansion.block("cat f", expansion.Outcome(status=0, output="$\u00a0x\n")),
        [],
    ),
}
# each text, whether it has an Evidence section and whether expand produced a
# block in it
SECTIONS: Mapping[str, tuple[str, bool, bool]] = {
    "a heading and a produced block": (f"## Evidence\n\n{GENERATED}", True, True),
    "a heading and no block": ("## Evidence\n\nOK\n", True, False),
    "a typed block": (f"## Evidence\n\n{TYPED}", True, False),
    "no heading": (f"{GENERATED}", False, False),
    "a block before the heading": (
        f"## Plan\n\n{GENERATED}\n## Evidence\n",
        True,
        False,
    ),
    "a block after the section": (
        f"## Evidence\n\n## Notes\n\n{GENERATED}",
        True,
        False,
    ),
    "a deeper heading stays inside": (
        f"## Evidence\n\n### Run\n\n{GENERATED}",
        True,
        True,
    ),
    "a same level heading ends it": (
        f"### Evidence\n\n### Run\n\n{GENERATED}",
        True,
        False,
    ),
    "a higher heading ends it": (f"### Evidence\n\n## Run\n\n{GENERATED}", True, False),
    "a bare deeper heading stays inside": (
        f"## Evidence\n\n###\n\n{GENERATED}",
        True,
        True,
    ),
    "a bare top heading ends it": (f"## Evidence\n\n#\n\n{GENERATED}", True, False),
    "a heading in the output": (
        f"## Plan\n\n{expansion.block('cat f', HEADINGS)}\n{GENERATED}",
        False,
        False,
    ),
    "a heading with no space": (f"#Evidence\n\n{GENERATED}", False, False),
    "seven hashes": (f"####### Evidence\n\n{GENERATED}", False, False),
    "four spaces of indent": (f"    ## Evidence\n\n{GENERATED}", False, False),
    "three spaces of indent": (f"   ## Evidence\n\n{GENERATED}", True, True),
    "a tab after the hashes": (f"##\tEvidence\n\n{GENERATED}", True, True),
    "a heading of another name": (f"## Evidences\n\n{GENERATED}", False, False),
    "a heading in lower case": (f"## evidence\n\n{GENERATED}", True, True),
}


class TestHandTyped(unittest.TestCase):
    """Which rows of a body are refused."""

    def test_each_case(self) -> None:
        """A command row is refused unless it is in a block expand produced."""
        for name, (text, refused) in CASES.items():
            with self.subTest(name):
                assert_that(evidence.hand_typed(text), equal_to(refused))


class TestSection(unittest.TestCase):
    """What the Evidence section of a body holds."""

    def test_each_case(self) -> None:
        """One definition of the heading says if there is a section and a block."""
        for name, (text, headed, made) in SECTIONS.items():
            with self.subTest(name):
                found = (evidence.has_section(text), evidence.has_produced(text))
                assert_that(found, equal_to((headed, made)))
