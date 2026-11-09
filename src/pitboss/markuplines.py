"""The check that a change adds no line to a ``.md`` or ``.rst`` file.

The owner's rule (pitboss#343, keyword markup-lines) is that lines only get
removed from the Markdown and reStructuredText files, and a rule goes into a
command's output or help text. ``pitboss plan-check`` refuses a PR whose diff
adds a line to such a file, except a changed line that is the removed line of
its hunk with characters deleted and none inserted or reordered (pitboss#373):
that is a removal, and the check names the rule once. A cut that leaves a
fragment (a line that starts with a closing mark or in the middle of a
sentence, a table row that lost its edge, a line that lost half of its
brackets, a sentence that lost its end) is a finding that names the line
(keyword: dangling-fragment, pitboss#358). The module reads no file and runs
nothing; it is given the output of ``git diff --numstat -z`` and of
``git diff -U0``.
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


def _pairs(hunk: str) -> Sequence[tuple[int, str, str]]:
    # the added lines of the hunk that are a removed line of it with characters
    # cut, each removed line used once and in order: (index among the added
    # lines, the added line, the removed line)
    rows = hunk.split("\n")
    removed = [each[1:] for each in rows if each.startswith("-")]
    found: list[tuple[int, str, str]] = []
    for index, new in enumerate(each[1:] for each in rows if each.startswith("+")):
        for at, old in enumerate(removed):
            if _subsequence(new, old):
                found.append((index, new, old))
                removed = removed[at + 1 :]
                break
    return found


def _hunks(patch: str) -> Sequence[tuple[str, int, str]]:
    # (path, number of the first added line, the hunk's rows) of every hunk
    found: list[tuple[str, int, str]] = []
    for each in re.split(r"^diff --git ", patch, flags=re.MULTILINE)[1:]:
        name = _path_of(each)
        parts = re.split(r"^(@@ .*)$", each, flags=re.MULTILINE)[1:]
        for header, rows in zip(parts[0::2], parts[1::2]):
            start = re.search(r"\+(\d+)", header)
            if name is not None and start is not None:
                found.append((name, int(start.group(1)), rows))
    return found


LEAD = re.compile(r"^(?:[-*+|>#]+|\d+[.)])?\s*")
BRACKETS = (("(", ")"), ("[", "]"), ("{", "}"))


def _unclosed(new: str, old: str) -> bool:
    # a bracket pair that was balanced in the old line and is not in the new one
    return any(
        old.count(a) == old.count(b) and new.count(a) != new.count(b)
        for a, b in BRACKETS
    )


def _table_row(text: str) -> bool:
    return text.startswith("|") and text.endswith("|")


def _dangling(new: str, old: str) -> str:
    # why the cut line `new` of `old` no longer reads as a whole, empty if it does
    text, was = new.strip(), old.strip()
    first, before = LEAD.sub("", text), LEAD.sub("", was)
    if not text or not first:
        return ""
    reasons = [
        (first[0] in ".,;:", "starts with a closing mark"),
        (first[0].islower() and not before[:1].islower(), "starts mid-sentence"),
        (_table_row(was) and not _table_row(text), "is a table row that lost its edge"),
        (_unclosed(text, was), "has an unclosed bracket"),
        (
            text.count("`") % 2 == 1 and was.count("`") % 2 == 0,
            "has an unclosed backtick",
        ),
        (
            was.endswith(".") and text[-1] not in ".:!?|`)",
            "lost the end of its sentence",
        ),
    ]
    return next((why for hit, why in reasons if hit), "")


def fragments(patch: str) -> Sequence[str]:
    """The cut lines of a patch that no longer read as a whole.

    Args:
        patch: the output of ``git diff -U0 --no-renames``.

    Returns:
        A finding for each added line of a .md or .rst file that only cuts
        characters from a removed line and leaves a fragment, naming its file
        and line (keyword: dangling-fragment, pitboss#358).
    """
    return [
        f"{CHECK}: `{path}` line {start + index} is a cut line that {why}:"
        f" `{new.strip()}`; cut the whole sentence, row or paragraph, with every"
        " reference to it, and leave no fragment (dangling-fragment)"
        for path, start, rows in _hunks(patch)
        if path.lower().endswith(SUFFIXES)
        for index, new, old in _pairs(rows)
        for why in [_dangling(new, old)]
        if why
    ]


def _cuts(patch: str) -> Mapping[str, int]:
    # the added lines of each file that only cut characters from a removed line
    found: dict[str, int] = {}
    for name, _, rows in _hunks(patch):
        found[name] = found.get(name, 0) + len(_pairs(rows))
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


def _added(numstat: str, patch: str) -> Sequence[str]:
    return [
        f"{CHECK}: `{path}` gets {added} added line{'' if added == 1 else 's'}; a"
        " change never adds a line to a .md or .rst file (lines are only removed;"
        " a span cut from a line is a removal)"
        for path, added, _ in _left(numstat, patch)
        if added
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
        line that counts, naming the number, and one for each cut line that
        leaves a fragment, naming the line (``fragments``); none for a file
        that only loses lines or cuts spans out of them.
    """
    return [*_added(numstat, patch), *fragments(patch)]


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
