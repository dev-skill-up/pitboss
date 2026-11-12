"""Whether a stored approval is still current for what it approved.

The keyword is current-for.

dev-skill-up/pitboss, bats-lang/quire#1120: a Plan approved at one digest stayed
"approved" after the Plan was revised, so no Plan re-review was offered and the
brief said "do not change it" of a Plan that had a newer digest. Every verdict,
check or approval the code stores against a digest or a head is read through this
one function, so none outlives the subject it was about:

* PLAN: a Plan approval or a ``plan-check`` against the digest of the Plan section.
* HEAD: an Execution approval against the PR's head.
* BODY: a review against the digest of the PR body it read.
* PROOF: an approval of an older head, current only when ``bats merge-proof`` of
  the reviewed SHA and the head says ``OK`` (``mergesonly.carries``); the caller
  states that proof, this function never takes an older head as current.
"""

import enum

from . import expansion


class Subject(enum.Enum):
    """What an approval, verdict or check was recorded against.

    Attributes:
        PLAN: the digest of the Plan section.
        HEAD: the SHA of the PR's head.
        BODY: the digest of the PR body.
    """

    PLAN = "plan"
    HEAD = "head"
    BODY = "body"


def current_for(subject: Subject, recorded: str, now: str) -> bool:
    """Whether something recorded against a subject is current for it.

    Args:
        subject: what was recorded against.
        recorded: the digest or SHA it records, empty when it records none.
        now: the digest or SHA of the subject now, empty when it is not known.

    Returns:
        PLAN: not ``expansion.section_changed`` (an unrecorded digest counts,
        as an older review's does; a digest from before the expanded blocks were
        collapsed counts, keyword: plan-digest-collapse). HEAD: the head starts
        with the recorded SHA, which must be given. BODY: the two digests do not
        differ when both are given.
    """
    if subject is Subject.PLAN:
        return not expansion.section_changed(recorded, now)
    if subject is Subject.HEAD:
        return bool(recorded) and now.startswith(recorded)
    return not (now and recorded and recorded != now)
