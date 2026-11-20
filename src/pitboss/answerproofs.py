"""The proofs of the decider's answers: P1, P7 and P8 (plan 6.3, keyword: one-path).

Each takes the parsed package and returns its findings, one line each, empty when
the property holds; ``CASES`` pairs each with the seed that breaks it.
"""

import ast


import re


from typing import Callable, Mapping, Sequence


from . import proofsource, worldfields


from .proofcase import Case, Proof, added, defines_text, edited, made_once, made_only_in


from .proofsource import Package

WAIT_WORDS = re.compile(r"wait|nobody acts|after |passed over|held", re.IGNORECASE)


ITEM_DECIDERS = frozenset({"decide_item", "decide_in"})


PURE = ("decide", "project", "render")


Fields = Sequence[ast.AnnAssign]


def _fields(package: Package, name: str) -> Fields:
    return worldfields.fields(proofsource.module(package, "answer"), name)


def _decision(bullet: str, broken: Callable[[Fields], str]) -> Proof:
    # a proof of the fields of ``Decision``: ``broken`` says what is wrong, or ""
    def proof(package: Package) -> Sequence[str]:
        said = broken(_fields(package, "Decision"))
        return [f"{bullet}: Decision {said}"] if said else []

    return proof


def _lacks(name: str) -> Callable[[Fields], str]:
    return lambda fields: (
        ""
        if name in {worldfields.field_name(each) for each in fields}
        else f"has no {name}"
    )


def _optional(fields: Fields) -> str:
    names = [
        worldfields.field_name(each)
        for each in fields
        if each.value is not None or "None" in ast.unparse(each.annotation)
    ]
    return f"has optional {names}" if names else ""


def _reasoned(fields: Fields) -> str:
    names = [worldfields.field_name(each) for each in fields]
    return "has a reason" if any("reason" in each for each in names) else ""


def _returns_none(function: ast.FunctionDef) -> bool:
    return function.returns is not None and "None" in ast.unparse(function.returns)


def only_item_returns_none(package: Package) -> Sequence[str]:
    """P7.5: only an item's decider returns ``None`` for an item.

    Args:
        package: the package.

    Returns:
        Each other public function of the decide module that does.
    """
    return [
        f"P7.5: decide.{name} returns None"
        for name, function in proofsource.functions_of(package, "decide").items()
        if _returns_none(function)
        and not name.startswith("_")
        and name not in ITEM_DECIDERS
    ]


def _typed(bullet: str, names: Sequence[str]) -> Proof:
    # no annotated field of the named classes of the answer module admits None
    def proof(package: Package) -> Sequence[str]:
        return [
            f"{bullet}: answer.{name}.{worldfields.field_name(each)} admits None"
            for name in names
            for each in _fields(package, name)
            if "None" in ast.unparse(each.annotation)
        ]

    return proof


def renderers_typed(package: Package) -> Sequence[str]:
    """P7.9: no renderer takes or returns a type that admits ``None``.

    Args:
        package: the package.

    Returns:
        Each renderer that does.
    """
    return [
        f"P7.9: render.{name} admits None"
        for name, function in proofsource.functions_of(package, "render").items()
        if _returns_none(function)
        or any("None" in each for each in proofsource.taken(function))
    ]


def _said(tree: ast.AST) -> Sequence[tuple[int, str]]:
    # each text, class name and assigned name of a module, with its line
    walked = proofsource.every_node(tree)
    names = [
        (node.lineno, node.name) for node in walked if isinstance(node, ast.ClassDef)
    ]
    assigned = [
        (node.lineno, proofsource.dotted(target))
        for node in walked
        if isinstance(node, ast.Assign)
        for target in node.targets
    ]
    return [*proofsource.texts_of(tree), *names, *assigned]


def no_wait_word(package: Package) -> Sequence[str]:
    """P7.10: no name or text of the decide, projection and render modules says a wait.

    Args:
        package: the package.

    Returns:
        Each that does.
    """
    return [
        f"P7.10: {name}:{line} says a wait: {text[:40]!r}"
        for name in PURE
        for line, text in _said(proofsource.module(package, name))
        if WAIT_WORDS.search(text)
    ]


def answer_is_work_or_none(package: Package) -> Sequence[str]:
    """P7.15: ``Answer`` is ``Work`` or ``NotEnoughWork``.

    Args:
        package: the package.

    Returns:
        What it is, when that is neither.
    """
    union = [
        ast.unparse(node.value)
        for node in ast.walk(proofsource.module(package, "answer"))
        if isinstance(node, ast.Assign)
        and [proofsource.dotted(each) for each in node.targets] == ["Answer"]
    ]
    return [] if union == ["Work | NotEnoughWork"] else [f"P7.15: Answer is {union}"]


def work_has_first(package: Package) -> Sequence[str]:
    """P7.16: ``Work`` has a required first decision.

    Args:
        package: the package.

    Returns:
        A finding when it has not.
    """
    first = [
        ast.unparse(each.annotation)
        for each in _fields(package, "Work")
        if worldfields.field_name(each) == "first" and each.value is None
    ]
    return (
        [] if first == ["Decision"] else ["P7.16: Work has no required first Decision"]
    )


def _guards_exhausted(arm: ast.AST) -> bool:
    # ``case world.Exhausted() if not ...``
    if not (isinstance(arm, ast.match_case) and isinstance(arm.guard, ast.UnaryOp)):
        return False
    pattern = arm.pattern
    return (
        isinstance(arm.guard.op, ast.Not)
        and isinstance(pattern, ast.MatchClass)
        and proofsource.dotted(pattern.cls) == "world.Exhausted"
    )


def _exhausted_arm(package: Package) -> str:
    # where the arm that guards the exhausted world makes the answer
    for node in ast.walk(proofsource.module(package, "decide")):
        if isinstance(node, ast.match_case) and _guards_exhausted(node):
            return f"decide:{node.body[0].lineno}"
    return "decide:none"


def exhausted_answer(package: Package) -> Sequence[str]:
    """P7.17: ``NotEnoughWork`` is made at one site, the exhausted arm of ``decide``.

    Args:
        package: the package.

    Returns:
        Where it is made, when that is not the one arm.
    """
    sites = proofsource.sites(package, "answer", "NotEnoughWork")
    return [] if sites == [_exhausted_arm(package)] else [f"P7.17: made at {sites}"]


CASES: Mapping[str, Case] = {
    "P1.1": Case(
        proof=made_only_in("P1.1", "answer", ["Decision"], "decide"),
        seed=added("render.py", "BAD = answer.Decision()"),
    ),
    "P1.2": Case(
        proof=made_only_in(
            "P1.2", "answer", ["Work", "NotEnoughWork", "Decided"], "decide"
        ),
        seed=added("project.py", "BAD = answer.Work()"),
    ),
    "P7.1": Case(
        proof=_decision("P7.1", _lacks("actor")),
        seed=edited("answer.py", "    actor: Actor\n", "    actors: Actor\n"),
    ),
    "P7.2": Case(
        proof=_decision("P7.2", _lacks("verb")),
        seed=edited("answer.py", "    verb: str\n", "    verbs: str\n"),
    ),
    "P7.3": Case(
        proof=_decision("P7.3", _optional),
        seed=edited("answer.py", "    lifts: str\n", "    lifts: str = ''\n"),
    ),
    "P7.4": Case(
        proof=_decision("P7.4", _reasoned),
        seed=edited(
            "answer.py", "    lifts: str\n", "    lifts: str\n    reason: str\n"
        ),
    ),
    "P7.5": Case(
        proof=only_item_returns_none,
        seed=edited(
            "decide.py",
            "def facts_of(record: world.PullRecord) -> pullfacts.PullFacts:",
            "def facts_of(record: world.PullRecord) -> pullfacts.PullFacts | None:",
        ),
    ),
    "P7.6": Case(
        proof=defines_text("P7.6", "decide", "_decided", "if found is not None:"),
        seed=edited(
            "decide.py",
            "if found is not None:\n            decided",
            "if found is None:\n            decided",
        ),
    ),
    "P7.7": Case(
        proof=_typed("P7.7", ["Decided"]),
        seed=edited(
            "answer.py",
            "    by_item: Mapping[str, Decision]\n",
            "    by_item: Mapping[str, Decision | None]\n",
        ),
    ),
    "P7.8": Case(
        proof=_typed("P7.8", ["Decision", "Work"]),
        seed=edited(
            "answer.py", "    first: Decision\n", "    first: Decision | None\n"
        ),
    ),
    "P7.9": Case(
        proof=renderers_typed,
        seed=edited(
            "render.py",
            "def decision_line(decision: answer.Decision) -> str:",
            "def decision_line(decision: answer.Decision | None) -> str:",
        ),
    ),
    "P7.10": Case(proof=no_wait_word, seed=added("decide.py", "SAID = 'nobody acts'")),
    "P7.15": Case(
        proof=answer_is_work_or_none,
        seed=edited(
            "answer.py",
            "Answer = Work | NotEnoughWork",
            "Answer = Work | NotEnoughWork | Decision",
        ),
    ),
    "P7.16": Case(
        proof=work_has_first,
        seed=edited(
            "answer.py", "    first: Decision\n", "    first: Decision = None\n"
        ),
    ),
    "P7.17": Case(
        proof=exhausted_answer,
        seed=added("project.py", "SECOND = answer.NotEnoughWork()"),
    ),
    "P7.18": Case(
        proof=made_once("P7.18", "world", "Exhausted", "readworld"),
        seed=added("render.py", "BAD = world.Exhausted(examined=[])"),
    ),
}
