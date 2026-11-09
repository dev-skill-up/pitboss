"""Whether a review's findings name a change to code, docs or tests (keyword: fix-round-kind).

A review that rejects the Plan gets a worker round that revises the Plan and
touches nothing else. Findings that name a file of the tree (a source, a doc or a
test) cannot be fixed by that round, so the sweep offers the fix round instead
(pitboss#390). A command quoted in a code span (it has a space) is a Plan row's
subject and names no change; nor does a link.
"""

import re

from . import sessionurl

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
