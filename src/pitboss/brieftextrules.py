"""The standing rules of the coordinator that the sweep prints (pitboss#444, item 2).

Each rule is about what an orchestrator says or does outside any PR, so pitboss
cannot see it done; it is printed at the end of every sweep as a reminder, and the
register (``rules.tsv``) names the sentence by its id. The tests pin the words.
"""

from typing import Mapping

RULES: Mapping[str, str] = {
    "A32": (
        "A32: no attribution block in a PR body, and never assign a PR or request"
        " its review from the owner."
    ),
    "A33": (
        "A33: a pin moves only by `relock-pins` or `pitboss pins-review`, never by"
        " a model's edit of the pin."
    ),
    "A34": (
        "A34: no shim is bundled for an engine that is too weak for the job; the"
        " job goes to a stronger model."
    ),
    "B3": (
        "B3: never tell the owner that nothing is running; read `pitboss slots"
        " list` first and name each slot."
    ),
    "B4": (
        "B4: a message that says a slot is idle is corrected at once from `pitboss"
        " slots list`, in the same thread."
    ),
    "B5": (
        "B5: run `pitboss slots next` again before each dispatch; an order read"
        " earlier is stale."
    ),
    "C8": (
        "C8: a workflow that reads a secret fails when it is unset; it never"
        " skips the step or falls back to an empty value."
    ),
    "D7": (
        "D7: never assume the owner acted; ask him, or read the PR, the issue or"
        " the log that shows it."
    ),
    "D8": (
        "D8: a ruling comment of the owner is standing approval; do not ask for it"
        " again."
    ),
    "D9": (
        "D9: every question to the owner comes with a markdown artifact that holds"
        " the evidence and the options."
    ),
    "D10": (
        "D10: an artifact or a log of CI is read through the new-environment"
        " thread, not by the orchestrator."
    ),
    "D15": (
        "D15: never resolve a card that waits on a human decision; the human"
        " resolves it."
    ),
}
REMINDERS = tuple(RULES.values())


def reminder(rule: str) -> str:
    """The sentence of one rule, as the sweep prints it.

    Args:
        rule: the id of the rule, ``A32`` to ``D15``.

    Returns:
        The sentence.
    """
    return RULES[rule]
