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
    texts = json.loads(
        (totalworld.FOLDER / "handbacks.json").read_text(encoding="utf-8")
    )
    lines = (
        (totalworld.FOLDER / "handback-labels.tsv")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    labelled = [
        int(fields[0])
        for fields in (line.split("\t") for line in lines if not line.startswith("#"))
        if fields[1] == "1"
    ]
    return [str(each) for each in texts], labelled


def _places(text: str) -> list[str]:
    paragraphs = [
        each.strip().replace("\n", " ") for each in text.split("\n\n") if each.strip()
    ][:40]
    return [
        place
        for para in paragraphs
        for place in (
            text,
            GOOD.replace("\n\n## Evidence", f"\n\n{para}\n\n## Evidence"),
            GOOD.replace("out.txt\n", f"out.txt\n  {para}\n"),
            GOOD.replace("out.txt\n", f"out.txt ({para})\n"),
            GOOD + f"- [2] {para}\n",
        )
    ]


class TestHeldOut(unittest.TestCase):
    """Every placement of every labelled disclosure is refused."""

    def test_444_755_of_755_placements_refused(self) -> None:
        """23 of 30 are disclosures; each of their placements is refused."""
        root = scratch.directory()
        (root / "out.txt").write_text("ok\n", encoding="utf-8")
        exists = handbackform.in_checkout(root)
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


class TestRules(unittest.TestCase):
    """Each rule, and what it refuses."""

    def test_444_each_fault_is_named(self) -> None:
        """Text before the items, a second items section, prose under Evidence.

        An open fence, a stray id.
        """
        exists = handbackform.in_checkout(None)
        url = "https://github.com/o/r/pull/3"
        for text, said in (
            (f"Done.\n## Items\n- [1] done | evidence: {url}\n", "text before"),
            (f"## Items\n- [1] done | evidence: {url}\n## Items\n", "second or late"),
            (
                f"## Items\n- [1] done | evidence: {url}\n## Evidence\nprose\n",
                "fenced blocks only",
            ),
            (
                f"## Items\n- [1] done | evidence: {url}\n## Evidence\n```\nopen\n",
                "not closed",
            ),
            ("nothing here", "no `## Items`"),
            (
                (
                    f"## Items\n- [1] done | evidence: {url}\n- [9] done | evidence:"
                    f" {url}\n"
                ),
                "not one of the ticket's",
            ),
            ("## Items\n- [1] done | evidence: not-run-here\n", "neither a GitHub run"),
        ):
            assert_that(
                "\n".join(handbackform.findings(text, ["1"], exists)),
                contains_string(said),
            )
        assert_that(exists("/etc/passwd"), equal_to(False))

    def test_444_each_rule_removed_lets_its_disclosure_through(self) -> None:
        """Prose in a done line, a pointer that is not one, an item with no line."""
        root = scratch.directory()
        (root / "out.txt").write_text("ok\n", encoding="utf-8")
        exists = handbackform.in_checkout(root)
        rest = "\n".join(GOOD.splitlines()[2:5]) + "\n"
        prose = (
            "## Items\n- [1] done, mostly (the Windows path is not run) | evidence:"
            " out.txt\n" + rest
        )
        loose = dataclasses.replace(
            handbackform.Form(),
            done=re.compile(r"- \[([\w.-]+)\] done.* \| evidence: (\S+).*"),
        )
        pointer = GOOD.replace("out.txt", "not-run-here")
        anything = dataclasses.replace(handbackform.Form(), url=re.compile(r"\S+"))
        short = "\n".join(GOOD.splitlines()[:3]) + "\n"
        for text, form, ids in (
            (prose, loose, IDS),
            (pointer, anything, IDS),
            (short, handbackform.Form(), ["1", "2"]),
        ):
            assert_that(
                (
                    bool(handbackform.findings(text, IDS, exists)),
                    handbackform.findings(text, ids, exists, form),
                ),
                equal_to((True, [])),
            )
