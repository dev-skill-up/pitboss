"""The check that a change adds no line to a ``.md`` or ``.rst`` file.

The owner's rule (pitboss#343, keyword markup-lines) is that lines only get
removed from the Markdown and reStructuredText files, and a rule goes into a
command's output or help text. ``pitboss plan-check`` refuses a PR whose diff
adds a line to such a file, except a changed line that is the removed line of
its hunk with characters deleted and none inserted or reordered (pitboss#373):
that is a removal, and the check names the rule once. The module reads no file
and runs nothing: the output of ``git diff --numstat -z`` and of ``git diff -U0``
is given.
"""

import json
import re
from typing import Mapping, Sequence

CHECK = "markup-lines"
SUFFIXES = (".md", ".rst")
NOTE = (
    f"{CHECK}: a changed line whose text is the removed line of its hunk with"
    " characters deleted and none inserted or reordered is a removal, not an"
    " added line"
)


def _subsequence(new: str, old: str) -> bool:
    # every character of `new`, in order, is a character of `old`
    rest = iter(old)
    return all(each in rest for each in new)


def _path_of(head: str) -> str | None:
    # the `+++ ` line of a file: `b/path`, maybe quoted; /dev/null has no path
    for line in head.split("\n"):
        if line.startswith("+++ "):
            name = line[4:].split("\t")[0]
            try:
                name = json.loads(name) if name.startswith('"') else name
            except ValueError:
                return None
            return name[2:] if name.startswith("b/") else None
    return None


def _matched(hunk: str) -> int:
    # how many added lines of the hunk are a removed line of it with characters
    # cut, each removed line used once and in order
    rows = hunk.split("\n")
    removed = [each[1:] for each in rows if each.startswith("-")]
    taken = 0
    for new in (each[1:] for each in rows if each.startswith("+")):
        for at, old in enumerate(removed):
            if _subsequence(new, old):
                taken += 1
                removed = removed[at + 1 :]
                break
    return taken


def _cuts(patch: str) -> Mapping[str, int]:
    # the added lines of each file that only cut characters from a removed line
    found: dict[str, int] = {}
    for each in re.split(r"^diff --git ", patch, flags=re.MULTILINE)[1:]:
        head, *hunks = re.split(r"^@@.*$", each, flags=re.MULTILINE)
        name = _path_of(head)
        if name is not None:
            found[name] = sum(_matched(hunk) for hunk in hunks)
    return found


def _counts(numstat: str) -> Sequence[tuple[str, int]]:
    # a record is `added TAB deleted TAB path`; a binary file has `-` for a count
    records = [each.split("\t", 2) for each in numstat.split("\0") if each]
    return [
        (path, int(added))
        for added, _, path in records
        if added.isdigit() and path.lower().endswith(SUFFIXES)
    ]


def _left(numstat: str, patch: str) -> Sequence[tuple[str, int, int]]:
    # (path, added lines that count, added lines that only cut a removed line)
    cuts = _cuts(patch)
    each = [(path, added, cuts.get(path, 0)) for path, added in _counts(numstat)]
    return [
        (path, added - min(added, cut), min(added, cut)) for path, added, cut in each
    ]


def findings(numstat: str, patch: str = "") -> Sequence[str]:
    """What a diff adds to the ``.md`` and ``.rst`` files.

    Args:
        numstat: the output of ``git diff --numstat -z --no-renames`` of the
            PR's head against its merge base with the base (a renamed file is
            a removal and an addition, so it adds its lines).
        patch: the output of ``git diff -U0 --no-renames`` of the same range. An
            added line that is a subsequence of a removed line of its hunk is a
            removal, not counted; with no patch every added line is counted.

    Returns:
        A finding for each ``.md`` or ``.rst`` file (in any case) with an added
        line that counts, naming the number; none for a file that only loses
        lines or cuts spans out of them.
    """
    return [
        f"{CHECK}: `{path}` gets {added} added line{'' if added == 1 else 's'}; a"
        " change never adds a line to a .md or .rst file (lines are only removed;"
        " a span cut from a line is a removal)"
        for path, added, _ in _left(numstat, patch)
        if added
    ]


def notes(numstat: str, patch: str) -> Sequence[str]:
    """The line that names the rule when a cut line was accepted.

    Args:
        numstat: as for ``findings``.
        patch: as for ``findings``.

    Returns:
        The rule, once, when some added line of a .md or .rst file was not
        counted because it only cuts characters from a removed line; else none.
    """
    return [NOTE] if any(cut for _, _, cut in _left(numstat, patch)) else []
