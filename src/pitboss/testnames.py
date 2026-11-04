"""The test names a PR body cites, against the head's tree (keyword: test-name).

A Plan or an Execution that cites ``test_...`` a head does not have was
written before the tests were (pitboss#189); ``test-name`` is the finding for
each such identifier. A name counts as there when the tree has a
``def <name>`` or a module ``<name>.py``.
"""

import os
import pathlib
import re
from typing import Collection, Iterator, Sequence

_CITED = re.compile(r"(?<![A-Za-z0-9_])test_[A-Za-z0-9_]+(?![A-Za-z0-9_])")
_DEF = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+(test_\w+)", re.MULTILINE)
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$", re.MULTILINE)
_FENCED = re.compile(
    r"^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?(?:^ {0,3}\1[`~]*[ \t]*$|\Z)",
    re.MULTILINE | re.DOTALL,
)
SECTIONS = ("plan", "execution")
# what a checkout holds that is not the head's: build output and installed packages
NOT_THE_HEADS = frozenset({"build", "dist", "node_modules", "site-packages"})


def _sections(body: str) -> Iterator[str]:
    # the text under each Plan or Execution heading, up to the next heading of
    # the same or a higher level; a line inside a fenced block is no heading
    fences = [each.span() for each in _FENCED.finditer(body)]
    headings = [
        each
        for each in _HEADING.finditer(body)
        if not any(low <= each.start() < high for low, high in fences)
    ]
    for index, title in enumerate(headings):
        if title.group(2).lower() not in SECTIONS:
            continue
        end = len(body)
        for later in headings[index + 1 :]:
            if len(later.group(1)) <= len(title.group(1)):
                end = later.start()
                break
        yield body[title.end() : end]


def cited(body: str) -> Sequence[str]:
    """The test names the Plan and Execution of a body cite.

    Args:
        body: the PR's body.

    Returns:
        Each distinct ``test_...`` identifier, in the order first cited.
    """
    found = [name for text in _sections(body) for name in _CITED.findall(text)]
    return list(dict.fromkeys(found))


def _python_files(root: pathlib.Path) -> Iterator[pathlib.Path]:
    for where, names, files in os.walk(root):
        names[:] = [
            each for each in names if each not in NOT_THE_HEADS and each[0] != "."
        ]
        yield from (
            pathlib.Path(where) / each for each in files if each.endswith(".py")
        )


def defined(root: pathlib.Path) -> Collection[str]:
    """The test names a checkout has.

    Args:
        root: the head's checkout.

    Returns:
        The name of each ``def test_...`` and of each ``test_....py`` module.
    """
    found: set[str] = set()
    for path in _python_files(root):
        found.add(path.stem)
        found.update(_DEF.findall(path.read_text(encoding="utf-8", errors="replace")))
    return found


def findings(name: str, body: str, root: pathlib.Path) -> Sequence[str]:
    """The findings for the test names a body cites that the head lacks.

    Args:
        name: what to call the body in a finding.
        body: the PR's body.
        root: the head's checkout.

    Returns:
        One finding for each cited name with no ``def`` in the tree.
    """
    wanted = cited(body)
    there = defined(root) if wanted else ()
    return [
        f"{name}: the Plan or Execution cites {each}, which the head has no"
        f" `def {each}` for: cite a test the head has (test-name)"
        for each in wanted
        if each not in there
    ]
