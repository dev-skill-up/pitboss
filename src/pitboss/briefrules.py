"""A printed brief never tells an agent to do what a register rule forbids (pitboss#444).

(Keyword: brief-contradiction, quire#1120.) The Plan revision of quire#1120 was
a change of the body only, but the brief's push line led the worker to push an
empty commit, which a standing rule forbids and which spent CI on a PR that is
not a draft. ``FORBIDDEN`` is the action words of the rules that forbid an
action (by the register's id); ``findings`` scans a printed brief, sentence by
sentence, for one of them that is not itself said as a prohibition.
"""

import re
from typing import Mapping, Sequence

FORBIDDEN: Mapping[str, re.Pattern[str]] = {
    "T221 no empty commit": re.compile(r"allow-empty|empty commit", re.I),
    "C13 no re-run to clear a flake": re.compile(
        r"re-?run (?:the |a |that )?(?:job|ci|workflow|check)|gh run rerun", re.I
    ),
    "B16 no close and reopen": re.compile(r"close and reopen|reopen the pr", re.I),
    "B2 no force push": re.compile(r"force[- ]push|push (?:-f|--force)", re.I),
    "A30 no scratch path": re.compile(r"(?<![\w.])/tmp/|/scratch/", re.I),
    "A12 no manual compare": re.compile(r"compare[^.;]*by hand|by eye", re.I),
}
NEGATED = re.compile(
    r"\b(?:never|no|not|nothing|don't|without|refuses?|refused|forbids?|instead of)\b"
    r"|\bno\b|\bnot\b",
    re.I,
)
SENTENCE = re.compile(r"[^.;\n]+")


def findings(brief: str) -> Sequence[str]:
    """The sentences of a brief that tell an agent to do a forbidden action.

    Args:
        brief: the printed brief.

    Returns:
        ``rule: sentence`` for each sentence with a forbidden action word and no
        word that makes it a prohibition.
    """
    return [
        f"{rule}: {each.strip()[:120]}"
        for each in SENTENCE.findall(brief)
        for rule, pattern in FORBIDDEN.items()
        if pattern.search(each) and not NEGATED.search(each)
    ]
