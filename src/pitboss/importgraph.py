"""The import graph of ``src/pitboss`` (keyword: test-selection, pitboss#331).

Each module's imports are read with ``ast``. Two links that no import states
are added to a file of the tests, because the tests run the commands by their
name and read the package from outside it:

* a file of the tests that holds a command's name as a string (``"nox"``) is
  taken to run that command, so it imports the module that registers it;
* a file of the tests that enumerates the commands, loads the installed
  entry point or reads its own files (``DYNAMIC``) imports every module of the
  package.
"""

import ast
import dataclasses
import itertools
from collections.abc import Iterable, Mapping, Sequence, Set

SOURCE = "src/pitboss/"
TESTS_PACKAGE = "pitboss.tests"
# a file of the tests with one of these runs the commands as a whole, or reads the
# package's own files: it is taken to import every module of the package
DYNAMIC = (
    "ENTRY_DATA",
    "collector",
    "entry_points",
    "runpy",
    '"-m", "pitboss"',
    "__file__",
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Source:
    """A file of the package, parsed.

    Attributes:
        module: its dotted name.
        package: the package its relative imports are relative to.
        syntax: its parsed text.
        text: its text.
    """

    module: str
    package: str
    syntax: ast.AST
    text: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Graph:
    """The modules of the package and what each imports.

    Attributes:
        edges: for each module, the modules it imports (the packages above an
            imported module included).
        unreadable: the paths of the files that could not be parsed.
    """

    edges: Mapping[str, Set[str]]
    unreadable: Set[str]


def module_of(path: str) -> str:
    """The module a file of the package is.

    Args:
        path: a path from the root of the repository.

    Returns:
        The dotted name; empty for a file that is not a ``.py`` file of
        ``src/pitboss``.
    """
    if not (path.startswith(SOURCE) and path.endswith(".py")):
        return ""
    names = path[: -len(".py")].split("/")[1:]
    return ".".join(names[:-1] if names[-1] == "__init__" else names)


def is_test(module: str) -> bool:
    """Whether a module is a test module (a ``test_`` file of the tests).

    Args:
        module: the dotted name.

    Returns:
        True for ``pitboss.tests.test_*``.
    """
    head, _, last = module.rpartition(".")
    return head == TESTS_PACKAGE and last.startswith("test_")


def in_tests(module: str) -> bool:
    """Whether a module is among the tests (a test module or a shared one).

    Args:
        module: the dotted name.

    Returns:
        True for ``pitboss.tests`` and what is under it.
    """
    return module == TESTS_PACKAGE or module.startswith(TESTS_PACKAGE + ".")


def base_of(node: ast.ImportFrom, package: str) -> str:
    """The module a ``from`` statement takes names from.

    Args:
        node: the statement.
        package: the package the file is in.

    Returns:
        The dotted name, with a relative import resolved.
    """
    if node.level == 0:
        return node.module or ""
    parts = package.split(".")
    above = parts[: len(parts) - node.level + 1]
    return ".".join([*above, *([node.module] if node.module else [])])


def imports_of(package: str, syntax: ast.AST) -> Iterable[str]:
    """The names a file imports, as dotted names that may be modules.

    Args:
        package: the package the file is in.
        syntax: its parsed source.

    Yields:
        Each name an ``import`` statement can bring in.
    """
    for node in ast.walk(syntax):
        if isinstance(node, ast.Import):
            yield from (each.name for each in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = base_of(node, package)
            yield base
            yield from (f"{base}.{each.name}" for each in node.names)


def parents_of(name: str) -> Iterable[str]:
    """A dotted name and the packages above it.

    Args:
        name: the dotted name.

    Returns:
        The name and each shorter prefix.
    """
    return itertools.accumulate(name.split("."), lambda above, last: f"{above}.{last}")


def registered_name(decorator: ast.expr, function: str) -> str:
    """The command name a decorator registers, if it is ``X.register(...)``.

    Args:
        decorator: the decorator.
        function: the decorated function's name, the default name.

    Returns:
        The name; empty when it is not a ``register``.
    """
    if not (
        isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and decorator.func.attr == "register"
    ):
        return ""
    names = [
        each.value.value
        for each in decorator.keywords
        if each.arg == "name" and isinstance(each.value, ast.Constant)
    ]
    return str(names[0]) if names else function


def commands_of(sources: Iterable[Source]) -> Mapping[str, str]:
    """The module that registers each command, by the command's name.

    Args:
        sources: the files of the package that are not tests.

    Returns:
        The command name (``name=`` of ``register``, else the function's) to
        the module.
    """
    return {
        registered_name(decorator, node.name): each.module
        for each in sources
        for node in ast.walk(each.syntax)
        if isinstance(node, ast.FunctionDef)
        for decorator in node.decorator_list
        if registered_name(decorator, node.name)
    }


def strings_of(syntax: ast.AST) -> Set[str]:
    """The string constants of a source.

    Args:
        syntax: the parsed source.

    Returns:
        Each string it holds.
    """
    return {
        node.value
        for node in ast.walk(syntax)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def package_of(module: str, path: str) -> str:
    """The package a file's relative imports are relative to.

    Args:
        module: the file's dotted name.
        path: its path.

    Returns:
        The module itself for an ``__init__`` file, else the package above it.
    """
    return module if path.endswith("__init__.py") else module.rpartition(".")[0]


def parse(sources: Mapping[str, str]) -> tuple[Sequence[Source], Set[str]]:
    """Parse the files of the package.

    Args:
        sources: the text of each ``.py`` file of ``src/pitboss``, by its path
            from the root of the repository.

    Returns:
        The files that parsed, and the paths of those that did not.
    """
    found: list[Source] = []
    unreadable: set[str] = set()
    for path, text in sources.items():
        module = module_of(path)
        try:
            syntax = ast.parse(text)
        except SyntaxError:
            unreadable.add(path)
        else:
            package = package_of(module, path)
            found.append(
                Source(module=module, package=package, syntax=syntax, text=text)
            )
    return found, unreadable


def runs_the_package(
    source: Source, library: Set[str], commands: Mapping[str, str]
) -> Set[str]:
    """The modules a file of the tests runs without importing them.

    Args:
        source: the file of the tests.
        library: the modules of the package that are not tests.
        commands: the module of each command, by its name.

    Returns:
        The modules of the commands it names, or every module when it
        enumerates the commands or reads the package's files.
    """
    named = {commands[each] for each in strings_of(source.syntax) if each in commands}
    whole = any(word in source.text for word in DYNAMIC)
    return named | (library if whole else set())


def imported_by(source: Source, known: Set[str]) -> Set[str]:
    """The modules of the package a file imports.

    Args:
        source: the file.
        known: the modules of the package.

    Returns:
        Them, the packages above an imported module included.
    """
    return {
        parent
        for name in imports_of(source.package, source.syntax)
        for parent in parents_of(name)
        if parent in known
    }


def build_graph(sources: Mapping[str, str]) -> Graph:
    """Read the imports of the package's files.

    Args:
        sources: the text of each ``.py`` file of ``src/pitboss``, by its path
            from the root of the repository (a file elsewhere is not read).

    Returns:
        The graph, with the two links no import states (see the module).
    """
    found, unreadable = parse(
        {path: text for path, text in sources.items() if module_of(path)}
    )
    known = {each.module for each in found}
    library = {each.module for each in found if not in_tests(each.module)}
    commands = commands_of([each for each in found if each.module in library])
    edges: dict[str, Set[str]] = {}
    for each in found:
        imported = imported_by(each, known)
        if in_tests(each.module):
            imported |= runs_the_package(each, library, commands)
        edges[each.module] = imported - {each.module}
    return Graph(edges=edges, unreadable=unreadable)


def dependents(graph: Graph, module: str) -> Set[str]:
    """The modules that import a module, directly or through others.

    Args:
        graph: the graph.
        module: the module.

    Returns:
        The module itself and everything that reaches it.
    """
    reached = {module}
    todo = [module]
    while todo:
        current = todo.pop()
        for each, imported in graph.edges.items():
            if current in imported and each not in reached:
                reached.add(each)
                todo.append(each)
    return reached


def tests_of(graph: Graph) -> Sequence[str]:
    """The test modules, in order.

    Args:
        graph: the graph.

    Returns:
        Their dotted names, sorted.
    """
    return sorted(each for each in graph.edges if is_test(each))
