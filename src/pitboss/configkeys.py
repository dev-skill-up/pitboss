"""A Plan whose diff adds a configuration key lists it in doc/example.toml.

Pitboss#365.

(Keyword: config-example.) Plan reviews of dev-skill-up/pitboss#363 rejected the
Plan twice for statements the change made false that the Impact list did not name:
a new table or key the loaders read that ``doc/example.toml`` does not list
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
    name = ""
    for each in patch.splitlines():
        if each.startswith("+++ b/"):
            name = each[6:]
        elif each.startswith("+") and not each.startswith("+++"):
            found.setdefault(name, []).append(each[1:])
    return found


def _keys(
    added: Mapping[str, Sequence[str]], example: str
) -> Sequence[tuple[str, str]]:
    # each key a loader's added lines read that the example does not name
    return [
        (name, key)
        for name, written in added.items()
        if LOADER.search(name)
        for each in written
        for key in KEY.findall(each)
        if not re.search(rf"\b{key}\b", example)
    ]


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
    found = [
        f"{CHECK}: `{name}` reads the key `{key}`, which {EXAMPLE} does not list with"
        f" its default: add it to the example ({CHECK})"
        for name, key in dict.fromkeys(_keys(added, example))
    ]
    return [*found, *_finding_row(body, added)]


def _finding_row(body: str, added: Mapping[str, Sequence[str]]) -> Sequence[str]:
    # the diff adds a way to find the configuration and the body has no row for it
    finds = any(FINDS.search(each) for written in added.values() for each in written)
    if not finds or ROW in body:
        return []
    return [
        f"{FIND_CHECK}: the diff changes how a command finds its configuration"
        f" and the Impact list has no row for `{ROW}` ({FIND_CHECK})"
    ]
