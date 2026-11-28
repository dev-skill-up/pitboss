"""The ``gh`` words of a write, read as a verb, a path and fields (keyword: landed)."""

import dataclasses
import itertools
import re
from typing import Mapping, Sequence

PR_VERBS = {"merge": "PR-MERGE", "ready": "PR-READY"}
MUTATION = re.compile(r"mutation\s*(?:\([^)]*\))?\s*\{\s*(\w+)")
FIELD_FLAGS = frozenset({"-f", "-F", "--field", "--raw-field"})


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Words:
    """One write, as its words say it.

    Attributes:
        verb: the HTTP method, or ``PR-MERGE`` and ``PR-READY`` for ``gh pr``.
        path: the path under ``https://api.github.com/`` (``repos/R/pulls/N``
            for ``gh pr``, ``graphql/NAME`` for the mutation NAME).
        fields: each field's values (``labels[]`` may have several).
        flags: the flags of a ``gh pr`` command.
    """

    verb: str
    path: str
    fields: Mapping[str, Sequence[str]]
    flags: Sequence[str] = ()


NO_FIELDS = Words(verb="", path="", fields={})


def value_of(write: Words, name: str) -> str:
    """The first value of a field of a write.

    Args:
        write: the write.
        name: the field.

    Returns:
        The value; empty when the write has no such field.
    """
    return next(iter(write.fields.get(name, [])), "")


def _fields(words: Sequence[str]) -> Mapping[str, Sequence[str]]:
    pairs = [
        given.partition("=")
        for flag, given in itertools.pairwise(words)
        if flag in FIELD_FLAGS and "=" in given
    ]
    return {
        key: [value for name, _, value in pairs if name == key] for key, _, _ in pairs
    }


def _mutation(fields: Mapping[str, Sequence[str]]) -> str:
    # the mutation a query names: ``mutation(...) { NAME(`` ("" for a query)
    return next(iter(MUTATION.findall(" ".join(fields.get("query", [])))), "")


def _api(words: Sequence[str]) -> Words | None:
    # every write of the package puts the path last, a query (graphql) excepted
    fields = _fields(words)
    if len(words) > 2 and words[2] == "graphql":
        return Words(verb="POST", path=f"graphql/{_mutation(fields)}", fields=fields)
    verbs = [given for flag, given in zip(words, words[1:]) if flag == "-X"]
    if len(words) < 3 or words[-1].startswith("-"):
        return None
    return Words(verb=verbs[-1] if verbs else "GET", path=words[-1], fields=fields)


def _is_flag(word: str) -> bool:
    return word.startswith("--")


def _pr(words: Sequence[str]) -> Words | None:
    # gh pr merge|ready NUMBER -R REPO [flags]
    if len(words) < 6 or words[2] not in PR_VERBS or "-R" not in words:
        return None
    repo = dict(itertools.pairwise(words))["-R"]
    flags = list(filter(_is_flag, words[4:]))
    path = f"repos/{repo}/pulls/{words[3]}"
    found = dataclasses.replace(NO_FIELDS, verb=PR_VERBS[words[2]])
    return dataclasses.replace(found, path=path, flags=flags)


def parse(words: Sequence[str]) -> Words | None:
    """Read the words of a write.

    Args:
        words: the ``gh`` command line.

    Returns:
        The write, None when the words are of neither shape the package writes
        with (``gh api`` and ``gh pr merge|ready``).
    """
    if list(words[:2]) == ["gh", "api"]:
        return _api(words)
    if list(words[:2]) == ["gh", "pr"]:
        return _pr(words)
    return None
