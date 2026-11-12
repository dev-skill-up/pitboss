"""A Plan whose diff adds a configuration key lists it in doc/example.toml (pitboss#365).

(Keyword: config-example.) Plan reviews of dev-skill-up/pitboss#363 rejected the
Plan twice for statements the change made false that the Impact list did not
name: a new table or key the loaders read that ``doc/example.toml`` does not list
with its default, and a new way for a command to find its configuration. The
module reads the diff and the example's text, as they are given.
"""

import re
from typing import Mapping, Sequence

EXAMPLE = "doc/example.toml"
CHECK = "config-example"
FIND_CHECK = "config-find"
LOADER = re.compile(r"(?:^|/)[a-z]*config[a-z]*\.py$")
KEY = re.compile(r"""(?:\.get\(\s*|_\w+\(\s*\w+,\s*)["']([a-z][a-z0-9_]*)["']""")
FINDS = re.compile(r"configsettle\.find_or_say|add_argument\(\s*[\"']--config[\"']")
ROW = "find_or_say"


def _added(patch: str) -> Mapping[str, Sequence[str]]:
    # the added lines of each file of a `git diff -U0` patch
    found: dict[str, list[str]] = {}
    path = ""
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            found.setdefault(path, []).append(line[1:])
    return found


def findings(body: str, patch: str, example: str) -> Sequence[str]:
    """What a diff adds to the configuration that the example or the Plan omits.

    Args:
        body: the PR's body, whose Impact list is searched for ``find_or_say``.
        patch: the output of ``git diff -U0 --no-renames`` of the PR.
        example: the text of ``doc/example.toml`` at the head, empty when none.

    Returns:
        A finding for each key a loader gains that the example does not list,
        naming it, and one when the diff adds a way to find the configuration
        (a call of ``configsettle.find_or_say`` or a ``--config`` option) and the
        body has no row for ``find_or_say``.
    """
    added = _added(patch)
    keys = [
        (path, key)
        for path, lines in added.items()
        if LOADER.search(path)
        for line in lines
        for key in KEY.findall(line)
        if not re.search(rf"\b{key}\b", example)
    ]
    found = [
        f"{CHECK}: `{path}` reads the key `{key}`, which {EXAMPLE} does not list with"
        f" its default: add it to the example ({CHECK})"
        for path, key in dict.fromkeys(keys)
    ]
    finds = any(FINDS.search(line) for lines in added.values() for line in lines)
    if finds and ROW not in body:
        found.append(
            f"{FIND_CHECK}: the diff changes how a command finds its configuration"
            f" and the Impact list has no row for `{ROW}` ({FIND_CHECK})"
        )
    return found
