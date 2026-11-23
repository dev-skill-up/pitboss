"""The capability rule: only capability packages reach the world (capability, #524).

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
from typing import AbstractSet, Callable, Iterator, Mapping, Sequence

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


def _made(path: str, node: ast.AST, rule: str, what: str) -> Finding:
    return Finding(path=path, line=getattr(node, "lineno", 0), rule=rule, what=what)


def _imports(path: str, node: ast.AST) -> Iterator[Finding]:
    match node:
        case ast.Import(names=names):
            modules = [each.name for each in names]
        case ast.ImportFrom(module=module, level=0):
            modules = [module or ""]
        case _:
            modules = []
    for name in modules:
        if name and not _allowed(name):
            yield _made(path, node, "E1", f"imports {name}")


def _allowed(name: str) -> bool:
    return any(name == each or name.startswith(each + ".") for each in ALLOWED)


def _banned_calls(path: str, node: ast.AST) -> Iterator[Finding]:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in BANNED_CALLS:
            yield _made(path, node, "E3", f"calls {node.func.id}")


def _attributes(path: str, node: ast.AST) -> Iterator[Finding]:
    if not isinstance(node, ast.Attribute):
        return
    handed = isinstance(node.value, ast.Name) and node.value.id == "args"
    said = (
        (node.attr in BANNED_ATTRIBUTES, "E3", f"uses .{node.attr}"),
        (node.attr in FRAMEWORK and handed, "E1", f"uses args.{node.attr}"),
    )
    for found, rule, what in said:
        if found:
            yield _made(path, node, rule, what)


def _dunder_strings(path: str, node: ast.AST) -> Iterator[Finding]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if "__" in node.value and node.value.strip("_") != "":
            yield _made(path, node, "E3", "a string names a dunder")


def _type_checking(path: str, node: ast.AST) -> Iterator[Finding]:
    if isinstance(node, ast.If) and node.orelse:
        test = node.test
        named = isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"
        dotted = isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        if named or dotted:
            yield _made(path, node, "E3", "runtime code under TYPE_CHECKING")


RULES: Sequence[Callable[[str, ast.AST], Iterator[Finding]]] = (
    _imports,
    _banned_calls,
    _attributes,
    _dunder_strings,
    _type_checking,
)


def _walk(path: str, tree: ast.AST) -> Iterator[Finding]:
    for node in ast.walk(tree):
        for rule in RULES:
            yield from rule(path, node)


def check(texts: Mapping[str, str]) -> Sequence[Finding]:
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
        found.extend(_walk(path, ast.parse(texts[path], filename=path)))
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
