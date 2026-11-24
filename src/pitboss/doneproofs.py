"""The proofs of the seeds the Done-when of #524 names (keyword: done-seeds).

Each takes the parsed package and returns its findings, one line each, empty when it
holds; ``CASES`` pairs each with the seed that breaks it (``proofseeds``). The
checker's own seeds are in ``tests/test_capability_seeds``.
"""

import ast
from typing import Mapping, Sequence

from .enummembers import members
from .proofcase import Case, Seed, added, made_only_in
from .proofsource import Package, module, searched

# what a caller of an act verb could hand it in place of the decision's own answer
FROM_THE_CALLER = frozenset({"step", "decision", "version", "pitboss-version"})
HAND_BACK_RECORDS = frozenset({"pitboss-hand-back", "hand-back-record"})


def _attributes(package: Package, name: str) -> set[str]:
    return {
        node.attr
        for node in ast.walk(module(package, name))
        if isinstance(node, ast.Attribute)
    }


def idle_has_an_event(package: Package) -> Sequence[str]:
    """P12.1: each member of ``Idle`` has an arm in ``idlewait.source_of``.

    Args:
        package: the package.

    Returns:
        Each member of ``Idle`` that no arm of ``source_of`` names.
    """
    named = _attributes(package, "idlewait")
    return [
        f"P12.1: Idle.{each} has no event in idlewait"
        for each in members(module(package, "steps"), "Idle")
        if each not in named
    ]


def no_hand_back_record(package: Package) -> Sequence[str]:
    """P12.2: nothing names a file or a store a hand-back is written to or read from.

    Args:
        package: the package.

    Returns:
        Each string that names one.
    """
    return [
        f"P12.2: {where}:{line} names a hand-back record {text!r}"
        for where, line, text in searched(package)
        if text in HAND_BACK_RECORDS
    ]


def act_takes_nothing_decided(package: Package) -> Sequence[str]:
    """P12.4: no act module reads a step, decision or version its caller hands it.

    The act decides by its own lookup (P8.4), so a decision made by another version
    of pitboss cannot be the one it carries out.

    Args:
        package: the package.

    Returns:
        Each string of an act module that names one.
    """
    return [
        f"P12.4: {where}:{line} reads {text!r} from the caller"
        for where, line, text in searched(package)
        if where.startswith("act") and text in FROM_THE_CALLER
    ]


def restore_plan_is_reached(package: Package) -> Sequence[str]:
    """P12.5: the flow names ``Task.RESTORE_PLAN``, so a re-pointed ticket is restored.

    A ticket re-pointed after its Plan was approved leaves an edited Plan under a
    ruling that stands (quire#1130); the flow answers with that task and not with
    a wait for the owner.

    Args:
        package: the package.

    Returns:
        A line when ``flowstate`` never names the task.
    """
    named = _attributes(package, "flowstate")
    return [] if "RESTORE_PLAN" in named else ["P12.5: flowstate never restores a Plan"]


def _hand_back_sites(package: Package) -> Sequence[str]:
    first = made_only_in("P12.3", "handbacks", ["HandedBack"], "handbackderive")
    return [each for each in first(package) if "handbacks:" not in each]


def hand_back_is_derived(package: Package) -> Sequence[str]:
    """P12.3: a ``HandedBack`` is made only from a PR's checks (``handbackderive``).

    Args:
        package: the package.

    Returns:
        Each place another module makes one (its own constants aside).
    """
    return _hand_back_sites(package)


def _seed(path: str, text: str) -> Seed:
    return added(path, text)


CASES: Mapping[str, Case] = {
    "P12.1": Case(
        proof=idle_has_an_event,
        seed=Seed(
            path="steps.py",
            old="    LOWER_PR_FIXES = enum.auto()\n",
            new="    LOWER_PR_FIXES = enum.auto()\n    NO_EVENT = enum.auto()\n",
        ),
    ),
    "P12.2": Case(
        proof=no_hand_back_record,
        seed=_seed("flow.py", 'RECORD = "pitboss-hand-back"\n'),
    ),
    "P12.3": Case(
        proof=hand_back_is_derived,
        seed=_seed(
            "flow.py",
            "from . import handbacks\n"
            'FORGED = handbacks.HandedBack(required=True, head="x", checked=())\n',
        ),
    ),
    "P12.5": Case(
        proof=restore_plan_is_reached,
        seed=Seed(
            path="flowstate.py",
            old="steps.Task.RESTORE_PLAN)  # keyword: restore-plan",
            new="steps.Task.REVISE_PLAN)  # keyword: restore-plan",
        ),
    ),
    "P12.4": Case(
        proof=act_takes_nothing_decided,
        seed=_seed("actverbs.py", 'SKEWED = "version"\n'),
    ),
}
