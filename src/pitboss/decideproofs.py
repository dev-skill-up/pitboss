"""The proofs of the decider's side: P1, P3, P7 and P8 (plan section 6.3).

Each takes the parsed package and returns its findings, one line each, empty when
the property holds (keyword: one-path).
"""

import ast
import re
from typing import AbstractSet, Iterator, Sequence

from . import proofsource
from .proofsource import Package

WAIT_WORDS = re.compile(r"wait|nobody acts|after |passed over|held", re.IGNORECASE)
REASONS = frozenset({"reason", "why", "because"})
SAYING = ("decide", "project", "render", "answer")
# decide_item, and its arm for a PR at a step, which the act verbs' kit tests alone
ITEM_DECIDERS = frozenset({"decide_item", "step_decision"})


def _answer_types(package: Package) -> AbstractSet[str]:
    return set(proofsource.classes(proofsource.module(package, "answer"))) - {"Actor"}


def _imported_from_answer(tree: ast.AST) -> AbstractSet[str]:
    return {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "answer"
        for alias in node.names
    }


def one_decider(package: Package) -> Sequence[str]:
    """P1: ``Decision`` and the answer's types are made only in ``decide``.

    Args:
        package: the package.

    Returns:
        Each call of a constructor outside the decide module.
    """
    types = _answer_types(package)
    found: list[str] = []
    for name, source in package.sources.items():
        short = name.removeprefix("pitboss.")
        if short == "decide":
            continue
        bare = _imported_from_answer(source.syntax) & types
        names = {f"answer.{each}" for each in types} | bare
        found.extend(
            f"P1: {short}:{node.lineno} makes {proofsource.called(node)}"
            for node in ast.walk(source.syntax)
            if isinstance(node, ast.Call) and proofsource.called(node) in names
        )
    return found


def _fields(tree: ast.AST, name: str) -> Sequence[ast.AnnAssign]:
    found = proofsource.classes(tree).get(name)
    body = [] if found is None else found.body
    return [each for each in body if isinstance(each, ast.AnnAssign)]


def _field_name(field: ast.AnnAssign) -> str:
    return proofsource.dotted(field.target)


def _raised(package: Package, name: str) -> Iterator[str]:
    for short, node in proofsource.nodes(package):
        if isinstance(node, ast.Raise) and node.exc is not None:
            target = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            if proofsource.dotted(target).endswith(name):
                yield short


def _caught(package: Package, name: str) -> Iterator[tuple[str, ast.ExceptHandler]]:
    for short, node in proofsource.nodes(package):
        if isinstance(node, ast.ExceptHandler) and node.type is not None:
            if proofsource.dotted(node.type).endswith(name):
                yield short, node


def _exits_nonzero(handler: ast.ExceptHandler) -> bool:
    for node in ast.walk(handler):
        if proofsource.called(node) == "SystemExit" and isinstance(node, ast.Call):
            status = node.args[0] if node.args else None
            if isinstance(status, ast.Constant) and status.value not in (0, None):
                return True
    return False


def read_failure(package: Package) -> Sequence[str]:
    """The one read failure: raised in ``retrying``, caught once, exits nonzero.

    Args:
        package: the package.

    Returns:
        What breaks it (P3 and P11).
    """
    found = [
        f"P3: ReadFailed is raised in {short}"
        for short in _raised(package, "ReadFailed")
        if short != "retrying"
    ]
    caught = list(_caught(package, "ReadFailed"))
    if [short for short, _ in caught] != ["cli_parser"]:
        found.append(f"P3: ReadFailed is caught in {[s for s, _ in caught]}")
    found.extend(
        f"P3: {short} catches ReadFailed without a nonzero exit"
        for short, handler in caught
        if not _exits_nonzero(handler)
    )
    return found


def no_partial_world(package: Package) -> Sequence[str]:
    """P3: ``World`` has no default and is made at one site, in ``readworld``.

    Args:
        package: the package.

    Returns:
        Each default, each other site and each break of the one read failure.
    """
    found = [
        f"P3: World.{_field_name(each)} has a default"
        for each in _fields(proofsource.module(package, "world"), "World")
        if each.value is not None
    ]
    sites = proofsource.calls_of(package, {"world.World", "World"})
    if [each.partition(":")[0] for each in sites] != ["readworld"]:
        found.append(f"P3: World is made at {sites}")
    return [*found, *read_failure(package)]


def _decision_shape(package: Package) -> Sequence[str]:
    fields = _fields(proofsource.module(package, "answer"), "Decision")
    names = {_field_name(each) for each in fields}
    found = [
        f"P7: Decision has no {each}" for each in sorted({"actor", "verb"} - names)
    ]
    for each in fields:
        said = ast.unparse(each.annotation)
        if each.value is not None or "None" in said or "Optional" in said:
            found.append(f"P7: Decision.{_field_name(each)} is optional")
        if _field_name(each) in REASONS:
            found.append(f"P7: Decision has a reason field {_field_name(each)}")
    return found


def _admits_none(function: ast.FunctionDef) -> bool:
    returns = function.returns
    return returns is not None and "None" in ast.unparse(returns)


def _takes_none(function: ast.FunctionDef) -> bool:
    said = [
        ast.unparse(each.annotation) for each in function.args.args if each.annotation
    ]
    return any("None" in each for each in said)


def _nothing_none(package: Package) -> Sequence[str]:
    found = [
        f"P7: answer:{node.lineno} admits None"
        for node in ast.walk(proofsource.module(package, "answer"))
        if isinstance(node, ast.AnnAssign) and "None" in ast.unparse(node.annotation)
    ]
    for name in ("project", "render"):
        tree = proofsource.module(package, name)
        found.extend(
            f"P7: {name}.{function.name} admits None"
            for function in proofsource.functions(tree).values()
            if _admits_none(function) or _takes_none(function)
        )
    deciding = proofsource.functions(proofsource.module(package, "decide"))
    found.extend(
        f"P7: decide.{name} admits None"
        for name, function in deciding.items()
        if _admits_none(function)
        and not name.startswith("_")
        and name not in ITEM_DECIDERS
    )
    return found


def _wait_words(package: Package) -> Sequence[str]:
    found: list[str] = []
    for name in SAYING:
        tree = proofsource.module(package, name)
        said = [*proofsource.texts_of(tree)]
        said.extend(
            (node.lineno, node.name)
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        )
        said.extend(
            (node.lineno, proofsource.dotted(target))
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            for target in node.targets
        )
        found.extend(
            f"P7: {name}:{line} says a wait: {text[:40]!r}"
            for line, text in said
            if WAIT_WORDS.search(text)
        )
    return found


def _not_enough_work(package: Package) -> Sequence[str]:
    found: list[str] = []
    answer = proofsource.module(package, "answer")
    union = [
        ast.unparse(node.value)
        for node in ast.walk(answer)
        if isinstance(node, ast.Assign)
        and [proofsource.dotted(each) for each in node.targets] == ["Answer"]
    ]
    if union != ["Work | NotEnoughWork"]:
        found.append(f"P7: Answer is {union}")
    first = [each for each in _fields(answer, "Work") if _field_name(each) == "first"]
    if [ast.unparse(each.annotation) for each in first] != ["Decision"]:
        found.append("P7: Work has no required first Decision")
    sites = proofsource.calls_of(package, {"answer.NotEnoughWork", "NotEnoughWork"})
    if sites != [_exhausted_arm(package)]:
        found.append(f"P7: NotEnoughWork is made at {sites}")
    made = proofsource.calls_of(package, {"world.Exhausted", "Exhausted"})
    if [each.partition(":")[0] for each in made] != ["readworld"]:
        found.append(f"P7: Exhausted is made at {made}")
    return found


def _exhausted_arm(package: Package) -> str:
    # where the arm ``case world.Exhausted() if not ...`` makes the answer
    for node in ast.walk(proofsource.module(package, "decide")):
        if isinstance(node, ast.match_case) and isinstance(node.guard, ast.UnaryOp):
            pattern = node.pattern
            if isinstance(pattern, ast.MatchClass) and isinstance(
                node.guard.op, ast.Not
            ):
                if proofsource.dotted(pattern.cls) == "world.Exhausted":
                    return f"decide:{node.body[0].lineno}"
    return "decide:none"


def no_wait(package: Package) -> Sequence[str]:
    """P7: no wait is said, and ``NotEnoughWork`` only when nothing is startable.

    Args:
        package: the package.

    Returns:
        Each break of (a) to (d).
    """
    return [
        *_decision_shape(package),
        *_nothing_none(package),
        *_wait_words(package),
        *_not_enough_work(package),
    ]


def _ends_total(function: ast.FunctionDef) -> bool:
    matches = [each for each in function.body if isinstance(each, ast.Match)]
    if not matches:
        return False
    last = matches[-1].cases[-1].body[-1]
    return (
        isinstance(last, ast.Expr) and proofsource.called(last.value) == "assert_never"
    )


def act_agrees(package: Package) -> Sequence[str]:
    """P8: act looks its verb up in the decisions, and ``totalverdict`` is gone.

    Args:
        package: the package.

    Returns:
        What breaks it.
    """
    found: list[str] = []
    lookup = proofsource.functions(proofsource.module(package, "gateverbs")).get(
        "lookup"
    )
    if lookup is None or not _ends_total(lookup):
        found.append("P8: gateverbs.lookup is no total match on the verb")
    elif ast.unparse(lookup.args.args[0].annotation or lookup) != "answer.Decided":
        found.append("P8: gateverbs.lookup does not take the decisions")
    found.extend(
        f"P8: {short}:{line} names totalverdict"
        for short, line, text in proofsource.searched(package)
        if "totalverdict" in text
    )
    if "pitboss.totalverdict" in package.sources:
        found.append("P8: the totalverdict module exists")
    return found
