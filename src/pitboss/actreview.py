"""The kinds of review ``act review`` writes and the digests it records (act-review).

A review of the Plan alone has no ``Execution:`` line, and a review after the Plan
was approved has ``Plan: approved (fixed)``, as the briefs of those kinds say; the
body and Plan digests are the ones of the body the reviewer read (the brief names
them), so a body edited after the read is seen by the sweep.
"""

from typing import Sequence

from . import actport, gradeline

GRADES = ("approved", "changes needed")
KINDS = ("full", "plan", "execution", "resolution", "fix-round", "relock")
PLAN_ALONE = "plan"
BOTH = ("full", PLAN_ALONE)


def kind_of(options: actport.Options) -> str:
    """The kind of review the options name.

    Args:
        options: the options of ``act review``.

    Returns:
        The ``--review-kind`` word, ``full`` when none is given.

    Raises:
        actport.Refused: a kind no review has.
    """
    kind = actport.option(options, "kind") if "kind" in options else "full"
    if kind not in KINDS:
        raise actport.Refused(f"kind is one of {', '.join(KINDS)}")
    return kind


def grades_of(kind: str, options: actport.Options) -> Sequence[str]:
    """The Plan, Execution and verdict grades of a review of a kind.

    Args:
        kind: the kind of review.
        options: ``plan``, ``execution`` and ``verdict``; a grade the kind does not
            write is not read.

    Returns:
        The three grades; a grade the kind does not write is ``approved``.

    Raises:
        actport.Refused: a grade the kind needs is not approved or changes needed.
    """
    reads = (kind in BOTH, kind != PLAN_ALONE, True)
    names = ("plan", "execution", "verdict")
    found = [
        actport.option(options, name) if read else GRADES[0]
        for name, read in zip(names, reads)
    ]
    if any(each not in GRADES for each in found):
        raise actport.Refused("a grade is approved or changes needed")
    return found


def shaped(words: str, kind: str, options: actport.Options) -> str:
    """A review in the lines its kind has, with the digests of the body it read.

    Args:
        words: the review as ``review_text`` wrote it.
        kind: the kind of review.
        options: ``body`` and ``plan-digest``, the digests the reviewer read (none
            keeps the digests of the body as it is now).

    Returns:
        The review.
    """
    lines = (_line(each, kind, options) for each in words.splitlines())
    return "\n".join(each for each in lines if each is not None)


def _line(line: str, kind: str, options: actport.Options) -> str | None:
    if line.startswith(gradeline.EXECUTION_PREFIX) and kind == PLAN_ALONE:
        return None
    if line.startswith(gradeline.PLAN_PREFIX) and kind not in BOTH:
        return gradeline.fixed_line(GRADES[0])
    for key, prefix in (("body", "Body: "), ("plan-digest", "Plan-digest: ")):
        if line.startswith(prefix) and key in options:
            return f"{prefix}{options[key]}"
    return line
