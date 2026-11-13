"""What each actor must write, in the words the checker reads (keyword: act-verbs).

The text the brief and the sweep carry (pitboss#444): every write to GitHub is a
``pitboss act`` verb, and each actor is told the verbs and the form of its own.
"""

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
