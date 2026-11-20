"""The ``--review-kind`` word of each review brief (grade-spellings).

``pitboss act review`` writes the grade lines of a kind and ``lint review`` checks
them with the same word, so the brief names the word and no line (rp#684: a
reviewer told to write a `Plan:` line posted ``Plan: ok``).
"""

from . import briefkind

Kind = briefkind.Kind
KIND_WORDS = {
    Kind.REVIEW_FULL: "full",
    Kind.REVIEW_PLAN: "plan",
    Kind.REVIEW_EXECUTION: "execution",
    Kind.REVIEW_RESOLUTION: "resolution",
    Kind.REVIEW_FIX_ROUND: "fix-round",
    Kind.REVIEW_RELOCK: "relock",
}
