"""The rule sentences of a review brief that its PR's files make apply."""

import unittest

from .briefmake import text
from .says import has_all, has_none
from ..brief import Kind
from .. import brieftextfolded, brieftextlint

DOCS = brieftextlint.MARKUP_LINES_REVIEW
SCAN = brieftextfolded.SYNTAX_SCAN_REVIEW
EVERY = [DOCS, SCAN]


class TestBriefWhen(unittest.TestCase):
    """A sentence about one kind of file is printed for a PR that changes one."""

    def test_a_pr_that_changes_only_code_has_none_of_them(self) -> None:
        """The brief of a PR of one module carries none of the file sentences."""
        for kind in (Kind.REVIEW_FULL, Kind.REVIEW_EXECUTION):
            has_none(text(kind, paths=["src/pitboss/wire.py"]), EVERY)

    def test_a_doc_brings_the_doc_sentence(self) -> None:
        """A changed .md file brings the sentence about doc lines."""
        has_all(text(Kind.REVIEW_FULL, paths=["README.md"]), [DOCS])

    def test_a_scan_brings_the_scan_sentence(self) -> None:
        """A changed scan module brings the sentence about syntax scans."""
        has_all(text(Kind.REVIEW_FULL, paths=["src/pitboss/syntaxscan.py"]), [SCAN])

    def test_files_not_read_leave_every_sentence(self) -> None:
        """A brief made with no file list is the whole one."""
        has_all(text(Kind.REVIEW_FULL), EVERY)
