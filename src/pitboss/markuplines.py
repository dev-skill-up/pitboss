"""The check that a change adds no line to a ``.md`` or ``.rst`` file.

Keyword: markup-lines. Owner rule (pitboss#343): lines only get removed from the Markdown and
reStructuredText files; a rule goes into a command's output or help text.
``pitboss plan-check`` refuses a PR whose diff adds a line to such a file. The
module reads no file and runs nothing: the output of ``git diff --numstat -z`` is
given.
"""

from typing import Sequence

CHECK = "markup-lines"
SUFFIXES = (".md", ".rst")


def _counts(numstat: str) -> Sequence[tuple[str, int]]:
    # a record is `added TAB deleted TAB path`; a binary file has `-` for a count
    records = [each.split("\t", 2) for each in numstat.split("\0") if each]
    return [
        (path, int(added))
        for added, _, path in records
        if added.isdigit() and path.lower().endswith(SUFFIXES)
    ]


def findings(numstat: str) -> Sequence[str]:
    """What a diff adds to the ``.md`` and ``.rst`` files.

    Args:
        numstat: the output of ``git diff --numstat -z --no-renames`` of the
            PR's head against its merge base with the base (a renamed file is
            a removal and an addition, so it adds its lines).

    Returns:
        A finding for each ``.md`` or ``.rst`` file (in any case) with an added
        line, naming the number; none for a file that only loses lines.
    """
    return [
        f"{CHECK}: `{path}` gets {added} added line{'' if added == 1 else 's'}; a"
        " change never adds a line to a .md or .rst file (lines are only removed)"
        for path, added in _counts(numstat)
        if added
    ]
