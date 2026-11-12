"""Every stop line of the verdict has a route: who acts on it, and with which verb.

The keyword is total-routes (pitboss#444). The first route whose pattern matches a line
is its route. The owner's routes are a closed list (a hold, ``paused-owner``, a
lock, a human reviewer). ``instructions()`` is the text the brief and the sweep
carry, built from the same table, so each actor is told the verb and the form the
checker reads.
"""

import dataclasses
import re
from typing import Mapping, Sequence

VERBS = (
    "merge",
    "arm",
    "disarm",
    "undraft",
    "review",
    "label",
    "hold",
    "unhold",
    "block",
    "override",
    "ticket",
    "ticket-edit",
    "close",
    "comment",
    "pr-create",
    "pr-edit",
    "update-branch",
    "rerun",
    "cancel",
    "dispatch-workflow",
    "push",
    "clean",
    "dispatch-next",
)
FORBIDDEN = re.compile(r"no row|not one the verdict|unknown to pitboss")
NEEDS_TEXT: Mapping[str, str] = {
    "reviewer": "act review",
    "worker": "act p",
    "orchestrator": "pitboss act",
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Route:
    """Who acts on the stop lines a pattern matches.

    Attributes:
        pattern: the start of the lines (a regular expression, matched at the start).
        actor: owner, pitboss, nobody, orchestrator, worker or reviewer.
        step: what the actor does.
        verb: the act verb of the step, if it has one.
    """

    pattern: str
    actor: str
    step: str
    verb: str = ""


def _route(pattern: str, actor: str, step: str, verb: str = "") -> Route:
    return Route(pattern=pattern, actor=actor, step=step, verb=verb)


_READ_AGAIN = (
    r"input |ticket \S+: not read|\w+: a required field is absent"
    r"|\w+=.*not of the (documented type|shape)|\w+=.*: not text|input:"
)
_TRIAGE = (
    "a red is triaged: `act dispatch-next` (one ticket for a shared red,"
    " the base's red is not the PR's)"
)
ROUTES: Sequence[Route] = (
    _route(r"hold:", "owner", "the hold ends by `act unhold`", "unhold"),
    _route(
        r"(labels=.*|auto_merge armed on a) ?.*paused-owner",
        "owner",
        "the owner removes paused-owner",
    ),
    _route(
        r"(locked|active_lock_reason)=", "owner", "the owner unlocks the conversation"
    ),
    _route(
        r"requested_(reviewers|teams)=",
        "owner",
        "the requested human review is given or withdrawn",
    ),
    _route(
        _READ_AGAIN,
        "pitboss",
        "read again (a failed or malformed read is never a GO); the same line on the"
        " next sweep",
    ),
    _route(
        r"(state|merged|merged_at|merged_by|closed_at)=",
        "nobody",
        "the PR is closed or merged: no action",
    ),
    _route(
        r"(number|url|\w+_url|html_url|base|head|user|author_association)=",
        "nobody",
        "not a PR of this queue: pitboss does not act on it",
    ),
    _route(
        r"draft=", "orchestrator", "`act undraft` when the Plan is approved", "undraft"
    ),
    _route(
        r"labels=|event (un)?labeled",
        "orchestrator",
        "`act label --remove`: only pitboss's labels are on a PR",
        "label",
    ),
    _route(
        r"auto_merge=",
        "orchestrator",
        "`act disarm`, then `act arm` when the verdict is GO",
        "disarm",
    ),
    _route(
        r"mergeable_state=dirty",
        "worker",
        "merge main into the branch, `act push`",
        "push",
    ),
    _route(
        r"mergeable_state=behind",
        "orchestrator",
        "`act update-branch`",
        "update-branch",
    ),
    _route(
        r"mergeable_state=unstable",
        "orchestrator",
        "a check that is not required is not green: `act dispatch-next` gives its"
        " triage",
        "dispatch-next",
    ),
    _route(
        r"mergeable_state=draft",
        "orchestrator",
        "`act undraft` when the Plan is approved",
        "undraft",
    ),
    _route(
        r"mergeable(_state)?=",
        "pitboss",
        "GitHub has not decided: read again on the next sweep",
    ),
    _route(
        r"check \S+ is |status \S+ is pending|check \S+: required and not reported",
        "pitboss",
        "wait for the run; the same line on the next sweep",
    ),
    _route(r"check |status ", "orchestrator", _TRIAGE, "dispatch-next"),
    _route(
        r"review: a formal request for changes",
        "owner",
        "a human's formal review is dismissed by that human",
    ),
    _route(
        r"review:|event ", "reviewer", "`act review` on the head as it is now", "review"
    ),
    _route(r"body: blocked by|blocked:", "pitboss", "wait for the named item to close"),
    _route(r"body:", "worker", "`act pr-edit` with the body in its form", "pr-edit"),
    _route(
        r"diff: .* added lines",
        "worker",
        "cut the added lines, `act push`; or `act override` naming the ruling",
        "override",
    ),
    _route(
        r"diff: .*Max-lines",
        "orchestrator",
        "`act override` naming the ruling, or the ticket is split before dispatch",
        "override",
    ),
    _route(
        r"diff: a workflow file",
        "worker",
        "the scratch run is cited in the body, `act pr-edit`",
        "pr-edit",
    ),
    _route(
        r"ticket: the body closes no ticket",
        "worker",
        "`act pr-edit`: the first line is `Fixes #N`",
        "pr-edit",
    ),
    _route(
        r"ticket ",
        "orchestrator",
        "the ticket is closed, locked or not an issue: `act close` the PR or"
        " `act pr-edit` to the open ticket",
        "close",
    ),
)


def route(line: str, routes: Sequence[Route] = ROUTES) -> Route | None:
    """The route of a stop line.

    Args:
        line: the stop line.
        routes: the table (the shipped one when none).

    Returns:
        The first route whose pattern matches the line, or None.
    """
    return next((each for each in routes if re.match(each.pattern, line)), None)


_ORCHESTRATOR = (
    "Every write to GitHub is a `pitboss act` verb: " + ", ".join(sorted(VERBS)) + "."
)
REQUIREMENTS: Mapping[str, Sequence[str]] = {
    "reviewer": (
        (
            "A review is posted only with `pitboss act review <pr>"
            " plan=approved|'changes needed' execution=... verdict=... findings=...`;"
            " it writes the head, the grades and the digests. A review typed as a"
            " comment is not read."
        ),
        (
            "After any event on the PR the review is of an older state: run"
            " `pitboss act review` again."
        ),
    ),
    "worker": (
        (
            "Every push is `pitboss act push`: the assigned branch, a commit with a"
            " change, the pre-push check printing `ok`."
        ),
        (
            "The PR is opened and its body changed only with `pitboss act pr-create`"
            " and `pitboss act pr-edit`. The first line is `Fixes #N`; the last `Head:`"
            " line is the head; no command of the `## Plan` section names a path of"
            " your machine (a scratchpad, a home, a mount)."
        ),
        "No line is added to a `.md` or `.rst` file; lines are only removed.",
        "A workflow file change cites its scratch run in the body.",
        (
            "The hand-back has one line per Done-when item: `- [N] done | evidence:"
            " <GitHub URL or path>`, `- [N] impossible | <command> | <output>`, or `-"
            " [N] owner | <request> | recommended: <answer> | until then: <what is done"
            " meanwhile>`."
        ),
    ),
    "orchestrator": (
        _ORCHESTRATOR,
        (
            "The next piece of work is what `pitboss act dispatch-next` returns, and"
            " nothing else."
        ),
    ),
}


def instructions(requirements: Mapping[str, Sequence[str]] = REQUIREMENTS) -> str:
    """What each actor must write, in the words the checker checks.

    Args:
        requirements: each actor's requirements (the shipped ones when none).

    Returns:
        The text the brief and the sweep carry.
    """
    parts = []
    for who, lines in requirements.items():
        parts.append(who.upper() + "\n" + "\n".join(f"- {each}" for each in lines))
    return "\n".join(parts) + "\n"
