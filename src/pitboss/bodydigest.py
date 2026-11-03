"""The digest of a PR body, recorded with a review (keyword: body-digest, pitboss#147).

GitHub's REST API gives no time for the last edit of a PR body (``updated_at``
moves with every label, push and comment), so a review records the body it
read as a ``Body: <digest>`` line, the first characters of the SHA-256 of the
body text. The sweep compares it with the body now; a body that differs after
the newest review of the head, the head not having moved, is ``older-body``.
"""

import hashlib
import re

PREFIX = "Body: "
LENGTH = 16
_LINE = re.compile(re.escape(PREFIX) + rf"(?P<digest>[0-9a-f]{{{LENGTH}}})")


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


def recorded(review: str) -> str:
    """The body digest a review comment records.

    Args:
        review: the review comment.

    Returns:
        The digest of its first ``Body:`` line, empty when it has none (a
        review that records no body is checked against the head alone).
    """
    matches = (_LINE.fullmatch(line.rstrip()) for line in review.splitlines())
    found = next((match for match in matches if match), None)
    return found.group("digest") if found else ""


def changed(recorded_digest: str, now: str) -> bool:
    """Whether a PR body is no longer the one a review recorded.

    Args:
        recorded_digest: the digest the review records, empty when it records none.
        now: the digest of the PR body now, empty when it is not checked.

    Returns:
        True when both are given and differ.
    """
    return bool(now and recorded_digest and recorded_digest != now)
