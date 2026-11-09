"""The findings that read the PR's head: its SHA and its files (pitboss#398).

(Keywords: evidence-head, lint-test.) ``plan-check`` gives the head's SHA, which
each Evidence block records, and the head's source files, which the diff
changes. The module reads no file and calls nothing.
"""

import pathlib
from typing import Sequence

from . import evidence, lintchange, selectdiff


def of_head(
    body: str, section: str, patch: str, tree: pathlib.Path, sha: str
) -> Sequence[str]:
    """What the body and the diff get wrong about the head.

    Args:
        body: the PR's body.
        section: its Plan section.
        patch: the output of ``git diff -U0 --no-renames`` of the PR.
        tree: the checkout of the head.
        sha: the head's SHA.

    Returns:
        The Evidence blocks expanded at another commit (``evidence``) and the
        changed finding functions with no cited new test (``lintchange``).
    """
    return [
        *evidence.stale_heads(body, sha),
        *lintchange.findings(section, patch, selectdiff.sources_of(str(tree))),
    ]
