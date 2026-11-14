"""The proofs of the decider's side: P1, P3, P7 and P8 (plan section 6.3).

Each takes the parsed package and returns its findings, one line each, empty when
the property holds (keyword: one-path).
"""

import ast
import re
from typing import Iterator, Sequence

from . import proofsource, worldfields
from .proofsource import Package

WAIT_WORDS = re.compile(r"wait|nobody acts|after |passed over|held", re.IGNORECASE)
REASONS = frozenset({"reason", "why", "because"})
SAYING = ("decide", "project", "render", "answer")
ITEM_DECIDERS = frozenset({"decide_item", "decide_in"})  # P7(b): an item alone


def one_decider(package: Package) -> Sequence[str]:
    """P1: ``decide.decide`` decides from one world and nothing else.

    Args:
        package: the package.

    Returns:
        What it takes, when that is not one ``world.World`` with no default.
    """
    decider = proofsource.defined(package, "decide", "decide")
    said = proofsource.taken(decider)
    if said == ["world.World"] and decider and not decider.args.defaults:
        return []
    return [f"P1: decide.decide takes {said}"]


_fields = worldfields.fields
_field_name = worldfields.field_name


def _caught(package: Package, name: str) -> Iterator[tuple[str, ast.ExceptHandler]]:
    for short, node in proofsource.nodes(package):
        if isinstance(node, ast.ExceptHandler) and node.type is not None:
            if proofsource.dotted(node.type).endswith(name):
                yield short, node


def _exits_nonzero(handler: ast.ExceptHandler) -> bool:
    for node in ast.walk(handler):
        if proofsource.called(node) == "SystemExit" and isinstance(node, ast.Call):
            status = proofsource.first_argument(node)
            if isinstance(status, ast.Constant) and status.value not in (0, None):
                return True
    return False


def read_failure(package: Package) -> Sequence[str]:
    """The one read failure: caught once, at the command entry, which exits nonzero.

    Args:
        package: the package.

    Returns:
        What breaks it (P3 and P11).
    """
    found = []
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
    """P3: no record ``World`` holds has a default; a failed read ends the command.

    Args:
        package: the package.

    Returns:
        Each default in the World's closure and each break of the one read failure.
    """
    return [*worldfields.defaults(package), *read_failure(package)]


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
    found.extend(
        f"P7: {name}.{function.name} admits None"
        for name in ("project", "render")
        for function in proofsource.functions_of(package, name).values()
        if _admits_none(function) or _takes_none(function)
    )
    deciding = proofsource.functions_of(package, "decide")
    found.extend(
        f"P7: decide.{name} admits None"
        for name, function in deciding.items()
        if _admits_none(function)
        and not name.startswith("_")
        and name not in ITEM_DECIDERS
    )
    return found


def _said(tree: ast.AST) -> Sequence[tuple[int, str]]:
    # each text, class name and assigned name of a module, with its line
    walked = proofsource.every_node(tree)
    return [
        *proofsource.texts_of(tree),
        *(
            (node.lineno, node.name)
            for node in walked
            if isinstance(node, ast.ClassDef)
        ),
        *(
            (node.lineno, proofsource.dotted(target))
            for node in walked
            if isinstance(node, ast.Assign)
            for target in node.targets
        ),
    ]


def _wait_words(package: Package) -> Sequence[str]:
    return [
        f"P7: {name}:{line} says a wait: {text[:40]!r}"
        for name in SAYING
        for line, text in _said(proofsource.module(package, name))
        if WAIT_WORDS.search(text)
    ]


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
    answered = [
        each
        for each in proofsource.sites(package, "answer", "NotEnoughWork")
        if each.startswith("decide:")
    ]
    if answered != [_exhausted_arm(package)]:
        found.append(f"P7: decide makes NotEnoughWork at {answered}")
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
    return bool(matches) and proofsource.ends_never(matches[-1].cases[-1].body)


def act_agrees(package: Package) -> Sequence[str]:
    """P8: act looks its verb up in the decisions, and ``totalverdict`` is gone.

    The lookup is a total match on the verb, and its verbs are the 27 that act
    applies. A verb in one and not the other is a finding, and so is ``run`` with
    no call of the lookup.

    Args:
        package: the package.

    Returns:
        What breaks it.
    """
    found: list[str] = []
    lookup = proofsource.defined(package, "gateverbs", "lookup")
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
    return [*found, *_every_verb(package)]


def _texts(values: Sequence[ast.expr | None]) -> set[str]:
    # the string constants among some expressions
    return {str(each.value) for each in values if isinstance(each, ast.Constant)}


def _words(tree: ast.AST, kinds: Sequence[str]) -> set[str]:
    # the words of the verbs' enums: each member's string value
    named = [
        kind.body for name, kind in proofsource.classes(tree).items() if name in kinds
    ]
    return _texts(
        [node.value for body in named for node in body if isinstance(node, ast.Assign)]
    )


def _table(tree: ast.AST) -> set[str]:
    # the words ``actverbs.VERBS`` applies
    tables = [
        node.value
        for node in proofsource.assigned(proofsource.statements(tree), "VERBS")
    ]
    return _texts(
        [key for each in tables if isinstance(each, ast.Dict) for key in each.keys]
    )


def _every_verb(package: Package) -> Sequence[str]:
    # P8: each of act's verbs is a member of the lookup's verbs, and act looks it up
    verbs = _words(proofsource.module(package, "gateverbs"), ("ItemVerb", "OwnVerb"))
    applied = _table(proofsource.module(package, "actverbs"))
    run = proofsource.defined(package, "actverbs", "run")
    looked = run is not None and any(
        proofsource.called(node) == "gateverbs.lookup" for node in ast.walk(run)
    )
    return [
        *(
            f"P8: act verb {each} is no verb the lookup matches"
            for each in sorted(applied - verbs)
        ),
        *(
            f"P8: verb {each} has nothing that applies it"
            for each in sorted(verbs - applied)
        ),
        *([] if looked else ["P8: actverbs.run does not look its verb up"]),
    ]
