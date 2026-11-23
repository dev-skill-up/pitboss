"""The capability rule: only capability packages reach the world (capability, #524).

``python -m pitboss.capability`` reads every ``.py`` file under the repository (not the
import graph, so a new package is read too) and says each place a module outside the
capability packages could read or change the world: an import that is not on the
allowlist, a banned name, a banned way to reach one without writing it, a string that
names a dunder, a runtime branch under ``TYPE_CHECKING`` and a use of the
``args.world`` the shell hands every command (processes and the environment). Each
finding is one line, ``path:line rule: what``; the exit status is the count's truth:
0 when there are none. The rules and what each closes are in the ticket
(dev-skill-up/pitboss#524).
"""

import ast
import dataclasses
import pathlib
import sys
from typing import AbstractSet, Callable, Iterator, Mapping, Sequence

from . import importgraph

# the packages and modules that may reach the world; nothing else may
CAPABILITY: AbstractSet[str] = frozenset()

# modules whose every use is a value or syntax: nothing in them reads
ALLOWED = frozenset(
    {
        "__future__",
        "abc",
        "argparse",
        "ast",
        "base64",
        "collections",
        "contextlib",
        "dataclasses",
        "decimal",
        "enum",
        "fnmatch",
        "fractions",
        "functools",
        "hashlib",
        "heapq",
        "itertools",
        "json",
        "logging",
        "math",
        "pathlib",
        "re",
        "shlex",
        "stat",
        "statistics",
        "string",
        "textwrap",
        "typing",
        "unicodedata",
        "urllib.parse",
    }
)
# modules that read or change the world, and the names of each that do neither
WORLD_MODULES: Mapping[str, AbstractSet[str]] = {
    "subprocess": frozenset(
        {"CalledProcessError", "TimeoutExpired", "CompletedProcess", "SubprocessError"}
    ),
    "os": frozenset({"fspath", "sep", "linesep", "PathLike", "path"}),
    "sys": frozenset({"stdout", "stderr", "exit", "version_info"}),
    "datetime": frozenset(
        {"datetime", "date", "time", "timedelta", "timezone", "UTC", "tzinfo"}
    ),
    "tomllib": frozenset({"loads", "TOMLDecodeError"}),
    "yaml": frozenset({"safe_load", "YAMLError"}),
    "gather.commands": frozenset({"add_argument", "set_parser", "ProcessRunner"}),
    "gather.api": frozenset({"Wrapper", "unique"}),
    "time": frozenset(),
    "tempfile": frozenset(),
    "shutil": frozenset(),
    "threading": frozenset(),
    "concurrent": frozenset(),
    "importlib": frozenset(),
    "urllib.request": frozenset(),
    "zipfile": frozenset(),
    "zoneinfo": frozenset(),
    "random": frozenset(),
    "unittest": frozenset(),
    "gather": frozenset(),
    "commander_data": frozenset(),
}
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
# attributes of any object that no pure module may use
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
        "parse_args",
        "parse_known_args",
        "parse_intermixed_args",
    }
)
# methods that read or change the world when called (a field of the same name is data)
BANNED_METHODS = frozenset(
    {
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "iterdir",
        "glob",
        "rglob",
        "exists",
        "is_file",
        "is_dir",
        "is_symlink",
        "mkdir",
        "unlink",
        "rmdir",
        "touch",
        "stat",
        "lstat",
        "resolve",
        "samefile",
        "readlink",
        "symlink_to",
        "rename",
        "open",
        "cwd",
        "home",
        "expanduser",
        "chmod",
        "now",
        "today",
        "utcnow",
        "isfile",
        "isdir",
        "islink",
        "getsize",
        "getmtime",
        "realpath",
        "abspath",
    }
)
FRAMEWORK = frozenset({"world"})


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


# the key of WORLD_MODULES that is the name or a package of it, longest first
def _world_key(name: str) -> str | None:
    found = (each for each in importgraph.parents_of(name) if each in WORLD_MODULES)
    return max(found, key=len, default=None)


def _allowed(name: str) -> bool:
    return any(name == each or name.startswith(each + ".") for each in ALLOWED)


def _imports(path: str, node: ast.AST) -> Iterator[Finding]:
    match node:
        case ast.Import(names=names):
            found = [(each.name, "") for each in names]
        case ast.ImportFrom(module=module, names=names, level=0):
            found = [(module or "", each.name) for each in names]
        case _:
            found = []
    for module, name in found:
        key = _world_key(module)
        if _allowed(module) or (key and (not name or name in WORLD_MODULES[key])):
            continue
        yield _made(path, node, "E1", f"imports {name or module} from {module}")


def _banned_names(path: str, node: ast.AST) -> Iterator[Finding]:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in BANNED_CALLS:
            yield _made(path, node, "E3", f"calls {node.func.id}")


def _banned_methods(path: str, node: ast.AST) -> Iterator[Finding]:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in BANNED_METHODS:
            yield _made(path, node, "E3", f"calls .{node.func.attr}")


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
    _banned_names,
    _banned_methods,
    _attributes,
    _dunder_strings,
    _type_checking,
)


# the world modules a file binds, by the name it uses for each
def _aliases(tree: ast.AST) -> Mapping[str, str]:
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for each in node.names:
                bound[each.asname or each.name.split(".")[0]] = (
                    each.name if each.asname else each.name.split(".")[0]
                )
    return bound


# each use of an imported world module that is not one of its safe names
def _uses(path: str, tree: ast.AST) -> Iterator[Finding]:
    bound = _aliases(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            key = _world_key(bound.get(node.value.id, ""))
            if key and node.attr not in WORLD_MODULES[key]:
                yield _made(path, node, "E1", f"uses {key}.{node.attr}")


def _walk(path: str, tree: ast.AST) -> Iterator[Finding]:
    yield from _uses(path, tree)
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
        if not {".venv", "build", ".git", "node_modules"}
        & set(path.relative_to(root).parts)
    }
    found = check(texts)
    for each in found:
        print(each)
    print(f"{len(found)} findings", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(pathlib.Path.cwd()))
