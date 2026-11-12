"""A .md or .rst file that a script writes is not hand-written (keyword: generated-markup, pitboss#433).

quire#1096 regenerated ``reports/quire-w3c-epub-tests.md`` with ``scripts/w3c-epub-tests-report.py``;
the digits changed in place and the markup-lines rule (no added line in a .md or .rst
file) refused the report, so the worker left it stale beside the regenerated json. A
file is *generated* when a tracked file that is not itself .md or .rst names its path:
the script that writes it. The rule applies as before to every other file.
"""

import re
from typing import Callable, Sequence

SUFFIXES = (".md", ".rst")
Grep = Callable[[str], Sequence[str]]


def scripted(grep: Grep) -> Callable[[str], bool]:
    """Whether a script of the repository names a file.

    Args:
        grep: the tracked files that hold a path as text (``git grep -l -F``).

    Returns:
        A function from a path to True when a file other than itself, and not a
        .md or .rst file, names it.
    """

    def generated(path: str) -> bool:
        return any(
            each != path and not each.lower().endswith(SUFFIXES) for each in grep(path)
        )

    return generated


def handwritten(
    numstat: str, patch: str, generated: Callable[[str], bool]
) -> tuple[str, str]:
    """The numstat and the patch without the files a script generates.

    Args:
        numstat: the output of ``git diff --numstat -z --no-renames``.
        patch: the output of ``git diff -U0 --no-renames``.
        generated: whether a path is generated.

    Returns:
        The same two texts with the records and the sections of generated .md and
        .rst files removed.
    """
    records = [
        each
        for each in numstat.split("\0")
        if not _drops(each.split("\t", 2)[-1], generated)
    ]
    sections = re.split(r"^(?=diff --git )", patch, flags=re.MULTILINE)
    kept = [each for each in sections if not _drops(_named(each), generated)]
    return "\0".join(records), "".join(kept)


def _named(section: str) -> str:
    found = re.match(r"diff --git a/(.*?) b/", section)
    return found.group(1) if found else ""


def _drops(path: str, generated: Callable[[str], bool]) -> bool:
    return path.lower().endswith(SUFFIXES) and generated(path)
