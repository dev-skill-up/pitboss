"""The check of a Plan's CI pointers against the tree (keyword: ci-pointer).

Quire#1060 cost two Plan reviews for two defects a command can see: a pointer
named the step ``Run the e2e group`` of a workflow whose step is ``Run e2e
tests``, and a new e2e spec had no pointer and was in no group. ``pitboss
plan-check`` refuses a pointer whose workflow file is at neither the base nor the
head, or whose job or step is not in the file (as written), a spec the diff adds
that no pointer's greppable string names, and one that no group list file names.
The module reads no file: the texts are given.
"""

import difflib
import fnmatch
import itertools
import json
import posixpath
import re
from typing import AbstractSet, Callable, Sequence

from . import ciworkflow, cipointer, plancheckconfig

CHECK = "ci-pointer"
Read = Callable[[str], str | None]
WILDCARD = re.compile(r"[*?\[]")


def _near(name: str, names: Sequence[str]) -> str:
    close = difflib.get_close_matches(name, sorted(names), n=3, cutoff=0.5)
    return f" (similar: {', '.join(f'`{each}`' for each in close)})" if close else ""


def _missing(
    point: cipointer.Pointer, kind: str, names: Sequence[str], known: AbstractSet[str]
) -> Sequence[str]:
    return [
        f"{CHECK}: Plan line {point.line} gives the {kind} `{each}`, which is no"
        f" {kind} of `{point.workflow}`{_near(each, sorted(known))}"
        for each in names
        if each not in known
    ]


def pointer_findings(
    pointers: Sequence[cipointer.Pointer], base: Read, head: Read
) -> Sequence[str]:
    """What the pointers name that the workflow files do not have.

    Args:
        pointers: the Plan's CI pointers.
        base: reads a file of the PR's base; None when it is not there.
        head: reads a file of the PR's head; None when it is not there.

    Returns:
        A finding for a workflow file at neither the base nor the head, and one
        for each job or step the head's file (the base's when the head has none)
        has no name for, exactly as written.
    """
    found: list[str] = []
    for each in pointers:
        text = head(each.workflow)
        text = base(each.workflow) if text is None else text
        if text is None:
            found.append(
                f"{CHECK}: Plan line {each.line} names the workflow"
                f" `{each.workflow}`, which exists at neither the base nor the head"
            )
            continue
        read = ciworkflow.read(text)
        found += _missing(each, "job", each.jobs, read.jobs)
        found += _missing(each, "step", each.steps, read.steps)
    return found


def _segments_match(path: str, pattern: str) -> bool:
    names, parts = path.split("/"), pattern.split("/")
    return len(names) == len(parts) and all(
        fnmatch.fnmatchcase(name, part) for name, part in zip(names, parts)
    )


def pattern_of(path: str, settings: plancheckconfig.PlanCheck) -> str | None:
    """The pattern of the specs that a path matches.

    Args:
        path: a path from the repository's root.
        settings: the ``[plan_check]`` table.

    Returns:
        The first pattern of ``specs`` that matches it; None when the path is no
        spec the repository configures.
    """
    return next((each for each in settings.specs if _segments_match(path, each)), None)


def _under_directory(path: str, pattern: str) -> str:
    # the name a group file gives the spec: its path under the pattern's directory
    parts = pattern.split("/")[:-1]
    fixed = list(itertools.takewhile(lambda each: not WILDCARD.search(each), parts))
    return posixpath.relpath(path, "/".join(fixed)) if fixed else path


def _strings(value: object) -> Sequence[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [each for item in value.values() for each in _strings(item)]
    if isinstance(value, list):
        return [each for item in value for each in _strings(item)]
    return []


def lists(text: str, path: str, relative: str) -> bool:
    """Whether a group list file names a spec.

    Args:
        text: the file's text: JSON, whose strings are the names; any other text
            names it where the name stands alone.
        path: the spec's path from the repository's root.
        relative: its path under its directory (``back.spec.js``).

    Returns:
        True when a string of the JSON is the path or the relative path, or, for
        a text that is no JSON, when either stands in it as a name.
    """
    try:
        return bool({path, relative} & set(_strings(json.loads(text))))
    except ValueError:
        pattern = r"(?<![\w./-])(?:{})(?![\w./-])"
        names = "|".join(re.escape(each) for each in (path, relative))
        return re.search(pattern.format(names), text) is not None


def spec_findings(
    added: Sequence[str],
    pointers: Sequence[cipointer.Pointer],
    settings: plancheckconfig.PlanCheck,
    head: Read,
) -> Sequence[str]:
    """What the specs the diff adds lack: a pointer, and a group.

    Args:
        added: the paths the diff adds.
        pointers: the Plan's CI pointers.
        settings: the ``[plan_check]`` table.
        head: reads a file of the PR's head; None when it is not there.

    Returns:
        A finding for each added spec that no pointer's greppable string
        contains (as its path or its file name), and one for each that none of
        the group list files names.
    """
    greppable = [each for point in pointers for each in point.greppable]
    found: list[str] = []
    for path in sorted(added):
        pattern = pattern_of(path, settings)
        if pattern is None:
            continue
        name = posixpath.basename(path)
        if not any(path in each or name in each for each in greppable):
            found.append(
                f"{CHECK}: the diff adds the spec `{path}`, which no CI pointer's"
                f" greppable string names (workflow, job, step and greppable"
                f" `{name}`)"
            )
        relative = _under_directory(path, pattern)
        texts = [head(each) for each in settings.groups]
        if settings.groups and not any(
            text is not None and lists(text, path, relative) for text in texts
        ):
            found.append(
                f"{CHECK}: the diff adds the spec `{path}`, which no group list"
                f" file ({', '.join(f'`{each}`' for each in settings.groups)})"
                f" names at the head, so no CI job runs it"
            )
    return found
