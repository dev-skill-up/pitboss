"""The lines ``act review`` writes in a repository's form (keyword: act-review-form)."""

from typing import Sequence

from . import reviewattempt


def _verdict_if_given(opened: Sequence[str], verdict: str) -> Sequence[str]:
    # the review's own verdict line goes only where the form has a verdict line of its
    # own; the gate reads a review by that line (keyword: one-path)
    given = any(reviewattempt.is_attempt(each) for each in opened)
    return [f"Verdict: {verdict}"] if given else []


def formed(words: str, form: Sequence[str], head: str, verdict: str) -> str:
    """A review in the lines the repository's reviews take (keyword: act-review-form).

    Args:
        words: the review as ``review_text`` wrote it.
        form: the repository's lines (``{sha}`` and ``{verdict}`` to fill); none
            leaves the review as it is.
        head: the full head SHA.
        verdict: the verdict, approved or changes needed.

    Returns:
        The form's lines, then the review without its own head line and without its
        own verdict line when the form has one (and with them again when the form
        has none of its own).
    """
    if not form:
        return words
    opened = [each.format(sha=head, verdict=verdict) for each in form]
    own = (f"Reviewed: {head}", *_verdict_if_given(opened, verdict))
    kept = [each for each in words.splitlines() if each not in own]
    return "\n".join([*opened, *kept])
