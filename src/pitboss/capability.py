"""The capability rule: only the capability packages reach the world (keyword: capability, #524).

``python -m pitboss.capability`` reads every ``.py`` file under the repository (not the
import graph, so a new package is read too) and says each place a module outside the
capability packages could read or change the world: an import that is not on the
allowlist, a banned name, a banned way to reach one without writing it, a string that
names a dunder, a runtime branch under ``TYPE_CHECKING`` and a use of the
``args.run``, ``args.safe_run`` or ``args.env`` the command framework hands every
command (all of them reach the world and none is a typed value). Each finding is
one line, ``path:line rule: what``; the exit status is the count's truth: 0 when there
are none. The rules and what each closes are in the ticket (dev-skill-up/pitboss#524).
"""

import ast
import dataclasses
import pathlib
import sys
from typing import AbstractSet, Iterator, Sequence

# the packages and modules that may reach the world; nothing else may
CAPABILITY: AbstractSet[str] = frozenset()

# the imports a module outside them may have: values and syntax, nothing that reads
ALLOWED = frozenset(
    {
        "__future__",
        "abc",
        "ast",
        "collections",
        "contextlib",
        "dataclasses",
        "datetime_types",
        "decimal",
        "enum",
        "fractions",
        "functools",
        "hashlib",
        "itertools",
        "json",
        "math",
        "re",
        "string",
        "textwrap",
        "typing",
        "urllib.parse",
    }
)
BANNED_CALLS = frozenset(
    {
        "open",
        "exec",
        "eval",
        "compile",
        "__import__",
        "input",
        "breakpoint",
        "getattr",
        "setattr",
        "delattr",
        "vars",
        "globals",
        "locals",
        "dir",
    }
)
BANNED_ATTRIBUTES = frozenset(
    {
        "__setattr__",
        "__class__",
        "__dict__",
        "__globals__",
        "__subclasses__",
        "__builtins__",
        "__members__",
        "__replace__",
        "attrgetter",
        "itemgetter",
        "methodcaller",
    }
)
FRAMEWORK = frozenset({"run", "safe_run", "env", "orig_run"})


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Finding:
    """One place a module could reach the world.

    Attributes:
        path: the file.
        line: the line.
        rule: the rule's name.
        what: what was found.
    """

    path: str
    line: int
    rule: str
    what: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} {self.rule}: {self.what}"


def _imported(node: ast.stmt) -> Iterator[str]:
    if isinstance(node, ast.Import):
        yield from (each.name for each in node.names)
    elif isinstance(node, ast.ImportFrom) and node.level == 0:
        yield node.module or ""


def _allowed(name: str) -> bool:
    return any(name == each or name.startswith(each + ".") for each in ALLOWED)


def _runtime_type_checking(node: ast.If) -> bool:
    test = node.test
    named = isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"
    dotted = isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    return (named or dotted) and bool(node.orelse)


def _findings(path: str, tree: ast.AST) -> Iterator[Finding]:
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        for name in _imported(node) if isinstance(node, ast.stmt) else ():
            if name and not _allowed(name):
                yield Finding(path=path, line=line, rule="E1", what=f"imports {name}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BANNED_CALLS:
                yield Finding(
                    path=path, line=line, rule="E3", what=f"calls {node.func.id}"
                )
        if isinstance(node, ast.Attribute):
            if node.attr in BANNED_ATTRIBUTES:
                yield Finding(
                    path=path, line=line, rule="E3", what=f"uses .{node.attr}"
                )
            if node.attr in FRAMEWORK and _is_args(node.value):
                yield Finding(
                    path=path, line=line, rule="E1", what=f"uses args.{node.attr}"
                )
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "__" in node.value and node.value.strip("_") != "":
                yield Finding(
                    path=path, line=line, rule="E3", what="a string names a dunder"
                )
        if isinstance(node, ast.If) and _runtime_type_checking(node):
            yield Finding(
                path=path, line=line, rule="E3", what="runtime code under TYPE_CHECKING"
            )


def _is_args(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id == "args"


def check(texts: dict[str, str]) -> Sequence[Finding]:
    """What the files given could do to the world.

    Args:
        texts: the text of each file, by its path from the repository's root.

    Returns:
        Each finding, in order, for the files outside the capability packages.
    """
    found: list[Finding] = []
    for path in sorted(texts):
        if pathlib.PurePosixPath(path).stem in CAPABILITY:
            continue
        found.extend(_findings(path, ast.parse(texts[path], filename=path)))
    return found


def main(root: pathlib.Path) -> int:
    """Print each finding under a root and say whether there are none.

    Args:
        root: the repository's root.

    Returns:
        0 when there is none, else 1.
    """
    texts = {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.py"))
        if not {".venv", "build", ".git", "node_modules"} & set(path.parts)
    }
    found = check(texts)
    for each in found:
        print(each)
    print(f"{len(found)} findings", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(pathlib.Path.cwd()))
