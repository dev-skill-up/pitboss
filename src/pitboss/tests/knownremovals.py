"""Each control taken out in turn: the 19 removals (cast-477-final.md, 5.5).

A removal is a kit with one control replaced by what pitboss had without it. The
cases that then miss are the ones that control holds; ``held`` runs them all.
"""

import dataclasses
import pathlib
from typing import Callable, Mapping, Sequence

from .. import actcore, actverbs, totalroutes, totalverdict
from ..totaljson import JsonMap
from . import captured
from .knownkit import Kit, Known, controls_of

Removal = Callable[[Kit], Kit]


def _rows(given: Kit, **changes: object) -> Kit:
    policy = dataclasses.replace(given.policy, **changes)  # type: ignore[arg-type]
    return dataclasses.replace(given, policy=policy, controls=controls_of(policy))


def _controls(given: Kit, **changes: object) -> Kit:
    controls = dataclasses.replace(given.controls, **changes)  # type: ignore[arg-type]
    return dataclasses.replace(given, controls=controls)


def _kit(given: Kit, **changes: object) -> Kit:
    return dataclasses.replace(given, **changes)  # type: ignore[arg-type]


def _verbs(given: Kit, **changes: actverbs.Verb) -> Kit:
    return dataclasses.replace(
        given,
        verbs={
            **given.verbs,
            **{key.replace("_", "-"): verb for key, verb in changes.items()},
        },
    )


def _go(action: str, pull: JsonMap, ctx: JsonMap) -> totalverdict.Answer:
    return totalverdict.Answer(word=totalverdict.GO)


def _nothing(*words: object) -> None:
    return None


def _none(*words: object) -> Sequence[str]:
    return []


def _naive_push(
    act: actcore.Act, target: actcore.Target, options: Mapping[str, str]
) -> str:
    worktree = options["worktree"]
    captured.finished(["git", "-C", worktree, "push", "-q", "origin", "HEAD"])
    return captured.run(["git", "-C", worktree, "rev-parse", "HEAD"]).stdout.strip()


def _first(act: actcore.Act, target: actcore.Target, options: Mapping[str, str]) -> str:
    want = options.get("want", "")
    return next(each.ref for each in act.work().items if want in ("", each.ref))


def _naive_items(body: str | None) -> Sequence[str]:
    return [
        line.lstrip("- ").strip()
        for line in str(body).split("## Done when", 1)[1].splitlines()
        if line.strip()
    ]


def _root_only(ticket: object) -> str:
    checkout: pathlib.Path = getattr(ticket, "checkout")
    return (checkout / "CLAUDE.md").read_text(encoding="utf-8")[:400]


REMOVALS: Mapping[str, Removal] = {
    "verdict_rows": lambda given: _controls(given, verdict=_go),
    "benign": lambda given: _rows(given, benign=frozenset()),
    "review_form": lambda given: _rows(
        given, review=lambda *words: "", plan=lambda *words: ""
    ),
    "body_rows": lambda given: _rows(given, body=_none),
    "not_overridable": lambda given: _controls(
        _rows(given, not_overridable=("\0",)), not_overridable=("\0",)
    ),
    "instructions": lambda given: _kit(
        given,
        requirements={
            **totalroutes.REQUIREMENTS,
            "orchestrator": ["Merge when the PR is ready."],
        },
    ),
    "act_gate": lambda given: _controls(given, hold_gate=_nothing, verdict=_go),
    "disarm": lambda given: _controls(given, disarm=_nothing),
    "block": lambda given: _verbs(given, block=lambda act, target, options: ""),
    "owner_gate": lambda given: _controls(given, owner_gate=_nothing),
    "push": lambda given: _verbs(given, push=_naive_push),
    "clean": lambda given: _verbs(
        given, clean=lambda act, target, options: "removable"
    ),
    "dispatch": lambda given: _verbs(given, dispatch_next=_first),
    "ticket_reader": lambda given: _controls(given, items=_naive_items),
    "started": lambda given: _controls(given, started=_none),
    "brief": lambda given: _kit(given, brief=_root_only, recount=_none),
    "rulecases": lambda given: _kit(
        given,
        add=lambda cases, new, encodings: next(iter(encodings)),
        diff_findings=_none,
    ),
    "handback": lambda given: _kit(given, findings=_none),
    "no_local_mutants": lambda given: _kit(given, registrations=_none),
}


def missed(given: Kit, cases: Mapping[str, Known]) -> Sequence[str]:
    """The cases that miss under a kit.

    Args:
        given: the kit.
        cases: the cases, by id.

    Returns:
        The names of the cases that are not true (an error is a miss).
    """
    found = []
    for name, known in cases.items():
        try:
            held = known.run(given)
        except Exception:  # noqa: B902 - a case that breaks under a removal misses
            held = False
        if held is not True:
            found.append(name)
    return found


def held(given: Kit, cases: Mapping[str, Known]) -> Mapping[str, Sequence[str]]:
    """The cases each removal makes miss.

    Args:
        given: the kit as shipped.
        cases: the cases, by id.

    Returns:
        Each removal's missed cases.
    """
    return {name: missed(removal(given), cases) for name, removal in REMOVALS.items()}
