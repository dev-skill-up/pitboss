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
# a cited line, `path/file.py:12` (not the `file:line: edited` line of an Impact list)
CITED = re.compile(
    r"(?<![\w./-])(?P<path>[\w.-]+(?:/[\w.-]+)*\.[A-Za-z0-9]+):(?P<line>\d+)\b"
)
DISPOSITION = re.compile(r"^\s*(?:[-*]\s+)?\S+:\d+: (?:not )?edited\b")
Read = Callable[[str], str | None]
WILDCARD = re.compile(r"[*?\[]")


def _near(wanted: str, known: Sequence[str]) -> str:
    close = difflib.get_close_matches(wanted, sorted(known), n=3, cutoff=0.5)
    return f" (similar: {', '.join(f'`{each}`' for each in close)})" if close else ""


def _missing(
    point: cipointer.Pointer, kind: str, given: Sequence[str], known: AbstractSet[str]
) -> Sequence[str]:
    return [
        f"{CHECK}: Plan line {point.line} gives the {kind} `{each}`, which is no"
        f" {kind} of `{point.workflow}`{_near(each, sorted(known))}"
        for each in given
        if each not in known
    ]


def _workflow_findings(
    point: cipointer.Pointer, base: Read, head: Read
) -> Sequence[str]:
    text = head(point.workflow)
    text = base(point.workflow) if text is None else text
    if text is None:
        return [
            f"{CHECK}: Plan line {point.line} names the workflow"
            f" `{point.workflow}`, which exists at neither the base nor the head"
        ]
    parsed = ciworkflow.read(text)
    return [
        *_missing(point, "job", point.jobs, parsed.jobs),
        *_missing(point, "step", point.steps, parsed.steps),
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
    return [
        each for point in pointers for each in _workflow_findings(point, base, head)
    ]


def form_findings(section: str) -> Sequence[str]:
    """The rows of a Plan that are meant as CI pointers and are none.

    Args:
        section: the Plan section.

    Returns:
        A finding for each such row (keyword: ci-pointer-form, pitboss#358),
        naming the row and the form a pointer needs.
    """
    return [
        f"{CHECK}: Plan line {number} is under `CI pointer rows` or names a workflow,"
        f" job or step, and is no CI pointer: `{text[:80]}`; {cipointer.FORM}"
        for number, text in cipointer.unrecognized(section)
    ]


def citation_findings(section: str, head: Read) -> Sequence[str]:
    """The lines a Plan cites that the head no longer has.

    Args:
        section: the Plan section.
        head: reads a file of the PR's head; None when it is not there.

    Returns:
        A finding (keyword: cited-line, pitboss#358) for each ``path:line`` in
        the Plan's prose whose file, at the head, is not there (a path with a
        directory) or has fewer lines; the ``file:line: edited`` lines of an
        Impact list are judged by the Impact check.
    """
    found: list[str] = []
    for number, text in cipointer.prose(section):
        if DISPOSITION.match(text):
            continue
        for cited in CITED.finditer(text):
            path, line = cited["path"], int(cited["line"])
            content = head(path)
            if content is None and "/" in path:
                found.append(_stale(number, cited[0], "the file is not at the head"))
            elif content is not None and line > len(content.splitlines()):
                total = len(content.splitlines())
                found.append(_stale(number, cited[0], f"the file has {total} lines"))
    return found


def _stale(number: int, cited: str, why: str) -> str:
    return (
        f"{CHECK}: Plan line {number} cites `{cited}`, which the head does not"
        f" bear out ({why}); cite the line where it is at the head"
    )


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
        if pattern is not None:
            found += _unnamed(path, greppable)
            found += _ungrouped(path, _under_directory(path, pattern), settings, head)
    return found


def _unnamed(path: str, greppable: Sequence[str]) -> Sequence[str]:
    name = posixpath.basename(path)
    if any(path in each or name in each for each in greppable):
        return []
    return [
        f"{CHECK}: the diff adds the spec `{path}`, which no CI pointer's"
        f" greppable string names (workflow, job, step and greppable `{name}`)"
    ]


def _ungrouped(
    path: str, relative: str, settings: plancheckconfig.PlanCheck, head: Read
) -> Sequence[str]:
    texts = [head(each) for each in settings.groups]
    listed = [
        text for text in texts if text is not None and lists(text, path, relative)
    ]
    if listed or not settings.groups:
        return []
    return [
        f"{CHECK}: the diff adds the spec `{path}`, which no group list"
        f" file ({', '.join(f'`{each}`' for each in settings.groups)})"
        f" names at the head, so no CI job runs it"
    ]
