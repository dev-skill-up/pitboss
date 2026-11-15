"""The rule sentences of a review brief that its PR's files make apply (brief-when).

A sentence about one kind of change (a doc, a lint, the order of steps, a syntax
scan, ``bats prcheck``) is printed only for a PR whose changed files are of that
kind; a PR whose files are not read gets every sentence.
"""

from typing import Mapping, Sequence

from . import (
    brieftextfolded,
    brieftextlint,
    brieftextorder,
    brieftextpins,
    brieftextprcheck,
    briefkind,
)
from .brieftext import SEPARATE_DRAFT_DRY, SEPARATE_DRY

# keyword: all-findings (pitboss#169): the reviews of a Plan try its commands
DRY_RUNNERS: Mapping[briefkind.Kind, str] = {
    briefkind.Kind.REVIEW_FULL: SEPARATE_DRY,
    briefkind.Kind.REVIEW_PLAN: SEPARATE_DRAFT_DRY,
    briefkind.Kind.REVIEW_RELOCK: brieftextpins.SEPARATE_PINS,
}
DOCS = (".md", ".rst")
ORDER_DOCS = ("sweep.md", "rules.md", "slots.md")
WORDS = {
    brieftextlint.MARKUP_LINES_REVIEW: DOCS,
    brieftextorder.ORDER_REVIEW: (*ORDER_DOCS, "order", "flow"),
    brieftextlint.LINT_TEST_REVIEW: ("lint", "check"),
    brieftextfolded.SYNTAX_SCAN_REVIEW: ("scan",),
}


def kept(lines: Sequence[str], repo: str, paths: Sequence[str] | None) -> Sequence[str]:
    """The sentences that apply to the PR.

    Args:
        lines: the scope sentences of a review brief.
        repo: the repository's ``owner/name``; only bats-lang repositories have
            ``bats prcheck``.
        paths: the files the PR changes, None when they are not read.

    Returns:
        The sentences the brief carries.
    """
    prcheck = repo.startswith("bats-lang/")
    return [
        line
        for line in lines
        if (line != brieftextprcheck.PRCHECK_REVIEW or prcheck)
        and (paths is None or line not in WORDS or _touches(paths, WORDS[line]))
    ]


def _touches(paths: Sequence[str], words: Sequence[str]) -> bool:
    return any(word in path for path in paths for word in words)
