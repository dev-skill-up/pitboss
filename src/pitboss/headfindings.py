"""The findings that read the PR's head: its SHA and its files (pitboss#398).

(Keywords: evidence-head, lint-test.) ``plan-check`` gives the head's SHA, which
each Evidence block records, and the head's source files, which the diff
changes. The module reads only the example of the configuration.
"""

import pathlib
from typing import Sequence

from . import configkeys, evidence, lintchange, selectdiff


def of_head(
    body: str, section: str, patch: str, head: tuple[pathlib.Path, str]
) -> Sequence[str]:
    """What the body and the diff get wrong about the head.

    Args:
        body: the PR's body.
        section: its Plan section.
        patch: the output of ``git diff -U0 --no-renames`` of the PR.
        head: the checkout of the head and its SHA.

    Returns:
        The Evidence blocks expanded at another commit (``evidence``) and the
        changed finding functions with no cited new test (``lintchange``).
    """
    tree, sha = head
    example = tree / configkeys.EXAMPLE
    shown = example.read_text(encoding="utf-8") if example.is_file() else ""
    return [
        *evidence.stale_heads(body, sha),
        *configkeys.findings(body, patch, shown),
        *lintchange.findings(section, patch, selectdiff.sources_of(str(tree))),
    ]
