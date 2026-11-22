"""The proofs of the pure modules and the one read: P2, P3, P5 and P6 (plan 6.3).

Each takes the parsed package and returns its findings, one line each, empty when
the property holds; ``CASES`` pairs each with the seed that breaks it (keyword:
one-path).
"""

import ast
from typing import Callable, Mapping, Sequence

from . import importgraph, proofsource, worldfields
from .proofcase import Case, Proof, Seed, added, made_once, returns, unparsed
from .proofsource import Package

SIGNATURE = "def read_world(reading: Reading, extent: modequestion.Extent) -> "
FAILED = (
    'print(f"READ FAILED: {{failed}}", file=sys.stderr)\n'
    "            raise SystemExit({}) from failed"
)
PURE = ("decide", "project", "render")


def _exits_nonzero(handler: ast.ExceptHandler) -> bool:
    for node in ast.walk(handler):
        if isinstance(node, ast.Call) and proofsource.called(node) == "SystemExit":
            status = proofsource.first_argument(node)
            if isinstance(status, ast.Constant) and status.value not in (0, None):
                return True
    return False


def _given(name: str, annotation: ast.expr | None) -> str:
    said = unparsed(annotation)
    return f"{name}.{said}" if said.isidentifier() and said[0].isupper() else said


def _aliases(package: Package) -> Mapping[str, Sequence[str]]:
    # each union a module names: ``answer.Answer`` is Work or NotEnoughWork
    found: dict[str, Sequence[str]] = {}
    for name in ("answer", "project"):
        for node in proofsource.statements(proofsource.module(package, name)):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.BinOp):
                members = ast.unparse(node.value).split(" | ")
                for target in node.targets:
                    found[f"{name}.{proofsource.dotted(target)}"] = [
                        each if "." in each else f"{name}.{each}" for each in members
                    ]
    return found


def _renderers(package: Package, returned: Sequence[str]) -> Sequence[str]:
    # each public renderer whose first argument is no projection's value
    aliases = _aliases(package)
    allowed = {*returned, *(m for each in returned for m in aliases.get(each, ()))}
    found = []
    for name, function in proofsource.functions_of(package, "render").items():
        first = function.args.args[0].annotation if function.args.args else None
        given = _given("render", first)
        if not name.startswith("_") and given not in allowed:
            found.append(f"render.{name} takes {given}, no projection's value")
    return found


def _reached(package: Package, wanted: Callable[[str], bool]) -> Sequence[str]:
    # each module the pure modules reach, imports of theirs that are wanted
    found = []
    for start in PURE:
        for name in sorted(proofsource.closure(package, start)):
            source = package.sources.get(name)
            if source is None:
                continue
            for each in importgraph.imports_of(source.package, source.syntax):
                if wanted(each):
                    found.append(f"{start} reaches {name}, which imports {each}")
    return found


def _module(top: str) -> Callable[[str], bool]:
    return lambda each: each.split(".")[0] == top


def _no_import(bullet: str, top: str) -> Proof:
    def proof(package: Package) -> Sequence[str]:
        return [f"{bullet}: {each}" for each in _reached(package, _module(top))]

    return proof


def _no_package_import(bullet: str, name: str) -> Proof:
    def proof(package: Package) -> Sequence[str]:
        found = _reached(package, lambda each: each == f"{proofsource.PACKAGE}.{name}")
        return [f"{bullet}: {each}" for each in found]

    return proof


def no_open(package: Package) -> Sequence[str]:
    """P2.4: the modules the pure modules reach call no ``open``.

    Args:
        package: the package.

    Returns:
        Each call.
    """
    return [
        f"P2.4: {name}:{node.lineno} calls open"
        for start in PURE
        for name in sorted(proofsource.closure(package, start))
        if name in package.sources
        for node in ast.walk(package.sources[name].syntax)
        if isinstance(node, ast.Call) and proofsource.called(node) == "open"
    ]


def no_default(package: Package) -> Sequence[str]:
    """P3.1: no field of a record the World holds has a default.

    Args:
        package: the package.

    Returns:
        Each field with one.
    """
    return [f"P3.1: {each}" for each in worldfields.defaults(package)]


def caught(package: Package) -> Sequence[tuple[str, ast.ExceptHandler]]:
    """Each handler of ``ReadFailed``, with the module it is in.

    Args:
        package: the package.

    Returns:
        The module and the handler.
    """
    return [
        (short, node)
        for short, node in proofsource.nodes(package)
        if isinstance(node, ast.ExceptHandler)
        and node.type is not None
        and proofsource.dotted(node.type).endswith("ReadFailed")
    ]


def caught_once(package: Package) -> Sequence[str]:
    """P3.4: the read failure is caught at one except site, in the command entry.

    Args:
        package: the package.

    Returns:
        Where it is caught, when that is not the one site.
    """
    where = [short for short, _ in caught(package)]
    return [] if where == ["cli_parser"] else [f"P3.4: ReadFailed is caught in {where}"]


def exits_nonzero(package: Package) -> Sequence[str]:
    """P3.5: the except site of the read failure exits nonzero.

    Args:
        package: the package.

    Returns:
        Each handler that does not.
    """
    return [
        f"P3.5: {short} catches ReadFailed and exits zero"
        for short, handler in caught(package)
        if not _exits_nonzero(handler)
    ]


def _projections(package: Package) -> Sequence[str]:
    return [
        _given("project", each.returns)
        for name, each in proofsource.functions_of(package, "project").items()
        if not name.startswith("_")
    ]


def one_projection(package: Package) -> Sequence[str]:
    """P5.1: each question has one projection function.

    Args:
        package: the package.

    Returns:
        Each question two functions answer.
    """
    returned = _projections(package)
    return [
        f"P5.1: two projections answer {each}"
        for each in sorted(set(returned))
        if returned.count(each) > 1
    ]


def renders_a_projection(package: Package) -> Sequence[str]:
    """P5.2: each renderer takes the type a projection returns.

    Args:
        package: the package.

    Returns:
        Each renderer that takes another.
    """
    return [f"P5.2: {each}" for each in _renderers(package, _projections(package))]


HANDLER = ("onepath", "answered")


BETWEEN = frozenset(
    {"project.what_next", "project.item_next", "mode.item_of", "assert_never"}
)


def nothing_between(package: Package) -> Sequence[str]:
    """P5.3: a mode's handler calls nothing between the decisions and its projection.

    Args:
        package: the package.

    Returns:
        Each call of the handler that is no projection.
    """
    handler = proofsource.defined(package, *HANDLER)
    calls = [] if handler is None else proofsource.every_node(handler)
    named = {
        proofsource.called(node)
        for node in calls
        if isinstance(node, ast.Call)
        and not proofsource.called(node).startswith(("_", "mode.question_of"))
    }
    return [f"P5.3: answered calls {each}" for each in sorted(named - BETWEEN)]


def no_command_ghapi(package: Package) -> Sequence[str]:
    """P6.2: no command module imports ``ghapi``.

    Args:
        package: the package.

    Returns:
        Each that does.
    """
    ghapi = f"{proofsource.PACKAGE}.ghapi"
    return [
        f"P6.2: {proofsource.short(name)} imports ghapi"
        for name, imported in sorted(package.edges.items())
        if ghapi in imported
        and (
            proofsource.short(name).endswith("_commands") or name.endswith(".commands")
        )
    ]


CASES: Mapping[str, Case] = {
    "P2.1": Case(
        proof=_no_import("P2.1", "subprocess"),
        seed=added("render.py", "import subprocess"),
    ),
    "P2.2": Case(
        proof=_no_import("P2.2", "urllib"),
        seed=added("render.py", "import urllib.request"),
    ),
    "P2.3": Case(
        proof=_no_import("P2.3", "socket"), seed=added("render.py", "import socket")
    ),
    "P2.4": Case(proof=no_open, seed=added("render.py", "OPENED = open('x')")),
    "P2.5": Case(
        proof=_no_package_import("P2.5", "ghapi"),
        seed=added("render.py", "from . import ghapi"),
    ),
    "P2.6": Case(
        proof=_no_package_import("P2.6", "ledger"),
        seed=added("render.py", "from . import ledger"),
    ),
    "P3.1": Case(
        proof=no_default,
        seed=Seed(
            path="shapes.py",
            old="    said: tuple[str, str]\n",
            new="    said: tuple[str, str] = ('', '')\n",
        ),
    ),
    "P3.2": Case(
        proof=made_once("P3.2", "world", "World", "readworld"),
        seed=added("render.py", "BAD = world.World()"),
    ),
    "P3.3": Case(
        proof=returns("P3.3", "readworld", "read_world", "world.World"),
        seed=Seed(
            path="readworld.py",
            old=SIGNATURE + "world.World:",
            new=SIGNATURE + "world.World | None:",
        ),
    ),
    "P3.4": Case(
        proof=caught_once,
        seed=added(
            "render.py", "try:\n    pass\nexcept retrying.ReadFailed:\n    pass"
        ),
    ),
    "P3.5": Case(
        proof=exits_nonzero,
        seed=Seed(
            path="cli_parser.py",
            old=FAILED.format(1),
            new=FAILED.format(0),
        ),
    ),
    "P5.1": Case(
        proof=one_projection,
        seed=added(
            "project.py",
            "def second(decided: answer.Decided) -> answer.Answer:\n"
            "    return what_next(decided)",
        ),
    ),
    "P5.2": Case(
        proof=renders_a_projection,
        seed=added("render.py", "def said(given: int) -> str:\n    return ''"),
    ),
    "P5.3": Case(
        proof=nothing_between,
        seed=Seed(
            path="onepath.py",
            old="return _listed(project.what_next(decided))",
            new="return _listed(project.what_next(decide.decide(decided)))",
        ),
    ),
    "P6.1": Case(
        proof=made_once("P6.1", "readworld", "read_world", "onepath"),
        seed=added("commands.py", "READ = readworld.read_world(None, None)"),
    ),
    "P6.2": Case(
        proof=no_command_ghapi, seed=added("next_commands.py", "from . import ghapi")
    ),
}
