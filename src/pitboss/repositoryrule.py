"""A repository's rule against a feature gives way to where the feature can live (pitboss#437).

(Keyword: repository-rule.) bats-lang/quire#1092 (require Android 10) was held
because pwa's CLAUDE.md allows only bug fixes and new platforms; the owner,
2026-11-09 20:52Z: a repository rule against a feature gives way when that
repository is the only place the feature can be done. A ``NOT STARTED``
hand-back that cites such a rule says where else the feature could live, or the
feature becomes a ticket in the repository that is the only place.
"""

import re

NOT_STARTED = re.compile(r"(?m)^\W*NOT STARTED\b")
CITES = re.compile(
    r"(?i)\b(?:CLAUDE\.md|repository'?s? rules?|forbids?|forbidden|disallowed|"
    r"not allowed|only (?:bug )?fixes)\b"
)
WHERE = re.compile(
    r"(?im)^\W*(?:could live in|can live in|the only place|ticket in)\b[^\n]*"
    r"\b[\w.-]+/[\w.-]+(?:#\d+)?"
)
REFUSED = (
    "refused: the hand-back stops at a repository rule against the feature, and"
    " says nowhere else the feature could live. A repository rule against a"
    " feature gives way when that repository is the only place the feature can be"
    " done (owner, 2026-11-09 20:52Z, quoted). Add a line `Could live in:"
    " <owner/repo>` naming the repository where the feature could live, or a line"
    " `Ticket in: <owner/repo>#N` for the ticket in the repository that is the"
    " only place"
)


def refusal(handback: str) -> str:
    """The refusal of a NOT STARTED hand-back that cites a rule and names no place.

    Args:
        handback: the hand-back text.

    Returns:
        The refusal; empty for any other hand-back and for one that names where
        else the feature could live.
    """
    if not NOT_STARTED.search(handback) or not CITES.search(handback):
        return ""
    return "" if WHERE.search(handback) else REFUSED
