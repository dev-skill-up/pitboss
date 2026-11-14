"""Whether a review comment is plain text, its lines strict (keyword: gated-review)."""

import re
from typing import Sequence

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


def literal_prefix(template: str) -> str:
    """The fixed text a template starts with.

    Args:
        template: a line template of the form.

    Returns:
        The text before the first ``{sha}`` or ``{verdict}``, stripped.
    """
    return re.split(r"\{(?:sha|verdict)\}", template)[0].strip()


def matches_strictly(lines: Sequence[str], template: str, count: int) -> bool:
    """Whether a template line matched once and its fixed text is on one line.

    Args:
        lines: the comment's lines.
        template: a line template of the form.
        count: how many lines the template matched.

    Returns:
        True when it did.
    """
    prefix = literal_prefix(template)
    containing = sum(1 for line in lines if prefix and prefix in line)
    return count == 1 and (not prefix or containing == 1)
