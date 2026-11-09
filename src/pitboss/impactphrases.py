"""The phrases a diff's Impact list needs rows for (keyword: impact-phrase, #317).

A Plan's Impact list was whatever its author thought to search for, and reviews
found the statements it missed (30 of 94 findings of one day were impact lists or
dispositions missed). ``pitboss plan-check`` builds the phrases from the diff
itself, from the lines it removes (the statements the change may make false) and
the lines it adds (the statements the change makes):

* each changed line of a ``.md`` or ``.rst`` file, and of a docstring or help
  string of a ``.py`` file (its first words, as written; an added line is read
  in the head's file, a removed one in the base's);
* each ``def``, ``class`` or constant on a changed line, in the forms
  ``come_first``, ``come-first`` and ``come first`` (``SWEEP_REMINDER`` and
  ``SWEEP REMINDER``), whatever the length of its name; a test name is one;
* the function or class whose docstring has a changed line, so its callers are
  searched.

``impact-phrase`` is the finding for each phrase that no Impact row searches (a
row searches it when one of its phrases holds it, in any case). The module reads
no file: the patch and readers of the base's and the head's files are given.
"""

import ast
import dataclasses
import re
import shlex
from typing import Callable, Mapping, Sequence

CHECK = "impact-phrase"
Read = Callable[[str], str | None]
MARKUP = (".md", ".rst")
HEADER = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
DEFINITION = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)")
CONSTANT = re.compile(r"^([A-Z][A-Z0-9_]*)\s*(?::[^=]+)?=")
WORDS = 6
MIN_WORDS = 3
LETTERS = re.compile(r"[A-Za-z]{4}")
LEADING = re.compile(r"""^[\s#*>|`"'.:-]+""")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Want:
    """A phrase the Impact list needs a row for.

    Attributes:
        phrase: the words, as written.
        where: the ``path:line`` of the changed line it comes from.
    """

    phrase: str
    where: str


Lines = Mapping[str, Sequence[tuple[int, str]]]


def _file(text: str, prefix: str) -> str:
    # the name a "---" or "+++" line gives, without its prefix; empty for no file
    name = text.split("\t")[0].removeprefix(prefix).strip('"')
    return "" if name == "/dev/null" else name


def changed(patch: str) -> tuple[Lines, Lines]:
    """The lines a ``git diff -U0`` removes and adds, by file.

    Args:
        patch: the diff.

    Returns:
        The removed lines by their file's old name, as ``(line in the base,
        text)``, and the added lines by their file's new name, as ``(line in
        the head, text)``.
    """
    gone: dict[str, list[tuple[int, str]]] = {}
    new: dict[str, list[tuple[int, str]]] = {}
    old = fresh = ""
    before = after = 0
    inside = False
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            inside = False
        elif not inside and line.startswith("--- "):
            old = _file(line[4:], "a/")
        elif not inside and line.startswith("+++ "):
            fresh = _file(line[4:], "b/")
        elif (header := HEADER.match(line)) is not None:
            inside = True
            before, after = int(header.group(1)), int(header.group(2))
        elif inside and line.startswith("-") and old:
            gone.setdefault(old, []).append((before, line[1:]))
            before += 1
        elif inside and line.startswith("+") and fresh:
            new.setdefault(fresh, []).append((after, line[1:]))
            after += 1
    return gone, new


def _first_words(text: str) -> str:
    # the start of a statement, as written, without the marks that open the line
    words = LEADING.sub("", text).split()[:WORDS]
    sentence = " ".join(words)
    enough = len(words) >= MIN_WORDS and LETTERS.search(sentence) is not None
    return sentence if enough else ""


def _name_forms(name: str) -> Sequence[str]:
    return list(dict.fromkeys([name, name.replace("_", "-"), name.replace("_", " ")]))


def _strings(source: str) -> Sequence[tuple[int, int, str]]:
    # the lines of each docstring and help string of a module: first, last, the
    # name of the function or class that owns a docstring (empty for a help string)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            doc = node.body[0] if node.body else None
            if isinstance(doc, ast.Expr) and isinstance(doc.value, ast.Constant):
                owner = "" if isinstance(node, ast.Module) else node.name
                found.append((doc.lineno, doc.end_lineno or doc.lineno, owner))
        elif isinstance(node, ast.keyword) and node.arg == "help":
            value = node.value
            found.append((value.lineno, value.end_lineno or value.lineno, ""))
    return found


def _python(path: str, lines: Sequence[tuple[int, str]], source: str) -> list[Want]:
    strings = _strings(source)
    found: list[Want] = []
    for number, text in lines:
        where = f"{path}:{number}"
        for first, last, owner in strings:
            if first <= number <= last:
                found.append(Want(phrase=_first_words(text), where=where))
                found.extend(Want(phrase=f, where=where) for f in _name_forms(owner))
        names = DEFINITION.match(text) or CONSTANT.match(text)
        if names:
            found.extend(Want(phrase=f, where=where) for f in _name_forms(names[1]))
    return found


def _phrases(lines: Lines, read: Read) -> Sequence[Want]:
    # the phrases of one side of the diff, read in the file of that side
    found: list[Want] = []
    for name, each in lines.items():
        if name.endswith(MARKUP):
            found.extend(
                Want(phrase=_first_words(t), where=f"{name}:{n}") for n, t in each
            )
        elif name.endswith(".py"):
            found.extend(_python(name, each, read(name) or ""))
    return found


def wanted(patch: str, base: Read, head: Read) -> Sequence[Want]:
    """The phrases the diff's removed and added lines need a row for.

    Args:
        patch: the diff (``git diff -U0``).
        base: reads a file of the PR's base; None when it is not there.
        head: reads a file of the PR's head; None when it is not there.

    Returns:
        Each distinct phrase (in any case), with the first line it came from.
    """
    gone, new = changed(patch)
    found = [*_phrases(gone, base), *_phrases(new, head)]
    kept = {each.phrase.lower(): each for each in reversed(found) if each.phrase}
    return sorted(kept.values(), key=lambda each: each.where)


def uncovered(
    wants: Sequence[Want], searched: Sequence[Sequence[str]]
) -> Sequence[str]:
    """The findings for the phrases no Impact row searches.

    Args:
        wants: the phrases the diff needs.
        searched: the phrases of each Impact row of the Plan.

    Returns:
        A finding for each phrase that none of the Impact rows' phrases holds,
        with the command that would search it.
    """
    held = [" ".join(each.lower().split()) for row in searched for each in row]
    return [
        f"{CHECK}: the diff changes {each.where}, and no Impact row searches"
        f" `{each.phrase}`: add `pitboss impact {shlex.quote(each.phrase)}` and a"
        " disposition for each hit"
        for each in wants
        if not any(each.phrase.lower() in phrase for phrase in held)
    ]
