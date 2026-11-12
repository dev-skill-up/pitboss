"""The hand-back form on held-out real hand-backs (keyword: handback-form, pitboss#444).

Thirty real hand-backs were drawn from the transcripts and labelled before the form
was written (``total/handback-labels.tsv``; 23 carry a disclosure: an open item as
part of the conclusion). Each paragraph of each labelled one is put in each of the
five places a conforming hand-back has, and the form must refuse every one.
"""

import dataclasses
import json
import re
import unittest

from hamcrest import assert_that, contains_string, empty, equal_to

from .. import handbackform
from . import scratch, totalworld
from .fakes import write

IDS = ["1", "2", "3", "4"]
GOOD = (
    "## Items\n- [1] done | evidence:"
    " https://github.com/bats-lang/quire/actions/runs/123/job/456\n- [2] done |"
    " evidence: out.txt\n- [3] impossible | command: `bats check` | output: error: no"
    " bats.lock\n- [4] owner | request: set the secret RELOCK_TOKEN | recommended: a"
    " fine-grained token with Contents write | until then: the relock PR lists the"
    " pin\n\n## Evidence\n```\n$ bats check\nok\n```\n"
)


def _sample() -> tuple[list[str], list[int]]:
    texts = json.loads(totalworld.folder_text("handbacks.json"))
    lines = totalworld.folder_text("handback-labels.tsv").splitlines()
    labelled = [
        int(fields[0])
        for fields in (line.split("\t") for line in lines if not line.startswith("#"))
        if fields[1] == "1"
    ]
    return [str(each) for each in texts], labelled


# where a paragraph goes in a good hand-back: what it replaces, and with what
PLACES = (
    ("\n\n## Evidence", "\n\n{para}\n\n## Evidence"),
    ("out.txt\n", "out.txt\n  {para}\n"),
    ("out.txt\n", "out.txt ({para})\n"),
)


def _checkout() -> handbackform.Exists:
    # a checkout that holds out.txt, as the form reads it
    root = scratch.directory()
    write(root / "out.txt", "ok\n")
    return handbackform.in_checkout(root)


def _places(text: str) -> list[str]:
    paragraphs = [
        each.strip().replace("\n", " ") for each in text.split("\n\n") if each.strip()
    ][:40]
    return [
        place
        for para in paragraphs
        for place in (
            text,
            *(GOOD.replace(old, new.format(para=para)) for old, new in PLACES),
            GOOD + f"- [2] {para}\n",
        )
    ]


class TestHeldOut(unittest.TestCase):
    """Every placement of every labelled disclosure is refused."""

    def test_444_755_of_755_placements_refused(self) -> None:
        """23 of 30 are disclosures; each of their placements is refused."""
        exists = _checkout()
        assert_that(handbackform.findings(GOOD, IDS, exists), empty())
        texts, labelled = _sample()
        placed = [place for index in labelled for place in _places(texts[index])]
        through = [
            place[:60]
            for place in placed
            if not handbackform.findings(place, IDS, exists)
        ]
        assert_that(
            (len(texts), len(labelled), len(placed), through),
            equal_to((30, 23, 755, [])),
        )


URL = "https://github.com/o/r/pull/3"
DONE = f"- [1] done | evidence: {URL}\n"
FAULTS = (
    (f"Done.\n## Items\n{DONE}", "text before"),
    (f"## Items\n{DONE}## Items\n", "second or late"),
    (f"## Items\n{DONE}## Evidence\nprose\n", "fenced blocks only"),
    (f"## Items\n{DONE}## Evidence\n```\nopen\n", "not closed"),
    ("nothing here", "no `## Items`"),
    (f"## Items\n{DONE}- [9] done | evidence: {URL}\n", "not one of the ticket's"),
    ("## Items\n- [1] done | evidence: not-run-here\n", "neither a GitHub run"),
)
PROSE = (
    "## Items\n- [1] done, mostly (the Windows path is not run) | evidence:"
    " out.txt\n"
)
LOOSE_DONE = re.compile(r"- \[([\w.-]+)\] done.* \| evidence: (\S+).*")


class TestRules(unittest.TestCase):
    """Each rule, and what it refuses."""

    def test_444_each_fault_is_named(self) -> None:
        """Text before the items, a second items section, prose under Evidence.

        An open fence, a stray id.
        """
        exists = handbackform.in_checkout(None)
        for text, said in FAULTS:
            assert_that(
                "\n".join(handbackform.findings(text, ["1"], exists)),
                contains_string(said),
            )
        assert_that(exists("/etc/passwd"), equal_to(False))

    def test_444_each_rule_removed_lets_its_disclosure_through(self) -> None:
        """Prose in a done line, a pointer that is not one, an item with no line."""
        exists = _checkout()
        rest = "\n".join(GOOD.splitlines()[2:5]) + "\n"
        prose = f"{PROSE}{rest}"
        loose = dataclasses.replace(handbackform.Form(), done=LOOSE_DONE)
        pointer = GOOD.replace("out.txt", "not-run-here")
        anything = dataclasses.replace(handbackform.Form(), url=re.compile(r"\S+"))
        short = "\n".join(GOOD.splitlines()[:3]) + "\n"
        cases = (
            (prose, loose, IDS),
            (pointer, anything, IDS),
            (short, handbackform.Form(), ["1", "2"]),
        )
        for text, form, ids in cases:
            assert_that(
                (
                    bool(handbackform.findings(text, IDS, exists)),
                    handbackform.findings(text, ids, exists, form),
                ),
                equal_to((True, [])),
            )
