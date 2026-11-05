"""Whether a review comment is plain text (keyword: gated-review)."""

import re

from . import sessionurl

_HTML = re.compile(r"<[A-Za-z/!]")
_LINK_DEFINITION = re.compile(r"^\s*\[[^\]]+\]:\s", re.MULTILINE)
_FENCE = "```"


def is_plain(body: str) -> bool:
    """Whether a comment is plain ASCII with no fence, HTML or link definition.

    Args:
        body: the comment.

    Returns:
        True when it is.
    """
    text = sessionurl.strip(body)
    return (
        text.isascii()
        and _FENCE not in text
        and not _HTML.search(text)
        and not _LINK_DEFINITION.search(text)
    )
