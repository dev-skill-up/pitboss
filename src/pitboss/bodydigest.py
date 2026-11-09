"""The digest of a PR body, recorded with a review (keyword: body-digest, pitboss#147).

GitHub's REST API gives no time for the last edit of a PR body (``updated_at``
moves with every label, push and comment), so a review records the body it
read as a ``Body: <digest>`` line, the first characters of the SHA-256 of the
body text. The sweep compares it with the body now; a body that differs after
the newest review of the head, the head not having moved, is ``older-body``.
"""

import hashlib
import re
from typing import Sequence

from . import plandigest

PREFIX = "Body: "
PLAN_PREFIX = "Plan digest: "  # the line of the Plan section (``plandigest``)
LENGTH = 16


def digest(body: str) -> str:
    """The digest of a PR body.

    Line endings are read as ``\\n`` and trailing white space is dropped, so
    the text a web edit saved (``\\r\\n``) and the text ``gh api --jq .body``
    prints (a final newline) have the digest of the text that was written.

    Args:
        body: the PR body.

    Returns:
        The first 16 hex digits of its SHA-256.
    """
    text = body.replace("\r\n", "\n").replace("\r", "\n").rstrip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:LENGTH]


def of_section(text: str) -> str:
    """The digest of a section of a PR body (keyword: plan-digest).

    Args:
        text: the section, empty when the body has none.

    Returns:
        Its digest, empty for no section.
    """
    return digest(plandigest.collapsed(text)) if text else ""


def legacy_of_section(text: str) -> str:
    """The digest a Plan section had before its expanded blocks were collapsed.

    Keyword: plan-digest-collapse (pitboss#358). Reviews and checks recorded
    before that change carry this digest, and are accepted for one published
    version (pitboss#399 drops the acceptance).

    Args:
        text: the section, empty when the body has none.

    Returns:
        The digest of the section as it is, empty for no section.
    """
    return digest(text) if text else ""


def accepted(text: str) -> Sequence[str]:
    """The digests a record of a Plan section may carry to be of this section.

    Args:
        text: the section, empty when the body has none.

    Returns:
        Its digest, and the digest it had before the blocks were collapsed
        (``legacy_of_section``); none for no section.
    """
    return [each for each in (of_section(text), legacy_of_section(text)) if each]


def section_changed(recorded_digest: str, text: str) -> bool:
    """Whether a Plan section is no longer the one a review recorded.

    Args:
        recorded_digest: the digest the review records, empty when it records none.
        text: the section now, empty when it is not checked.

    Returns:
        True when both are given and the digest differs from every accepted one.
    """
    return bool(text and recorded_digest and recorded_digest not in accepted(text))


def recorded_after(review: str, prefix: str) -> str:
    """The digest a review comment records on its first line with a prefix.

    Args:
        review: the review comment.
        prefix: what the line starts with (``Body: ``, ``Plan digest: ``).

    Returns:
        The digest of its first such line (the prefix and exactly 16 hex
        digits), empty when it has none.
    """
    line = re.compile(re.escape(prefix) + rf"(?P<digest>[0-9a-f]{{{LENGTH}}})")
    matches = (line.fullmatch(each.rstrip()) for each in review.splitlines())
    found = next((match for match in matches if match), None)
    return found.group("digest") if found else ""


def recorded(review: str) -> str:
    """The body digest a review comment records.

    Args:
        review: the review comment.

    Returns:
        The digest of its first ``Body:`` line, empty when it has none (a
        review that records no body is checked against the head alone).
    """
    return recorded_after(review, PREFIX)


def changed(recorded_digest: str, now: str) -> bool:
    """Whether a PR body is no longer the one a review recorded.

    Args:
        recorded_digest: the digest the review records, empty when it records none.
        now: the digest of the PR body now, empty when it is not checked.

    Returns:
        True when both are given and differ.
    """
    return bool(now and recorded_digest and recorded_digest != now)
