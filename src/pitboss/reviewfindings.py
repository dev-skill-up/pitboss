"""Whether a review names a change to code, docs or tests (keyword: fix-round-kind).

A review that rejects the Plan gets a worker round that revises the Plan and
touches nothing else. Findings that name a file of the tree (a source, a doc or a
test) cannot be fixed by that round, so the sweep offers the fix round instead
(pitboss#390). A command quoted in a code span (it has a space) is a Plan row's
subject and names no change; nor does a link.
"""

import re
from typing import AbstractSet, Sequence

from . import sessionurl, shapes

_LINK = re.compile(r"https?://\S+")
_COMMAND = re.compile(r"`[^`\n]*\s[^`\n]*`")
_EXTENSIONS = "py|rst|md|toml|json|ya?ml|txt|tsv|cfg|ini|sh|js|ts|bats"
_FILE = re.compile(rf"(?<![\w/.-])(?:[\w.-]+/)*[\w-]+\.(?:{_EXTENSIONS})\b")
_TREE = re.compile(r"(?<![\w/.-])(?:src|tests|doc|docs|plugins|scripts|templates)/")


def names_change(review: str) -> bool:
    """Whether a review comment names a file of the tree.

    Args:
        review: the review comment.

    Returns:
        True when, outside links and quoted commands, it names a file with a
        code, doc or test extension or a path under a directory of the tree.
    """
    text = _COMMAND.sub(" ", _LINK.sub(" ", sessionurl.strip(review)))
    return bool(_FILE.search(text) or _TREE.search(text))


def named_by(
    comments: Sequence[shapes.Comment], trusted: AbstractSet[str], when: str
) -> bool:
    """Whether the review comment written at a time names a file of the tree.

    Args:
        comments: the PR's issue comments.
        trusted: the author associations whose comments count.
        when: when the review was written (ISO 8601).

    Returns:
        True when a trusted comment of that time names a change.
    """
    return any(
        names_change(each.body)
        for each in comments
        if each.created_at == when and each.author_association in trusted
    )
