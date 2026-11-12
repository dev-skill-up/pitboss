"""The verbs of ``pitboss act``, by name (keyword: act-verbs).

``VERBS`` is the one table: the command line, the route table's verbs and the
completeness test all read it. Every verb but ``ack`` and ``clean`` passes the
owner gate and the hold gate first (``gate_first``). ``dispatch-next`` is here: it answers the one
next piece of work, and for a ticket with a checkout it writes the brief (every
rule file on the ticket's paths, the verdict's gates on them, and the
instructions of the route table), refused when the recount finds a file missing.
"""

import dataclasses
import functools
import pathlib
from typing import Callable, Mapping

from . import (
    actgit,
    actpull,
    actwrite,
    dispatchnext,
    rulecases,
    rulecount,
    rulefiles,
    ticketreader,
    totalroutes,
)
from .actcore import Act, Options, Refused, Target, cap_of, gate

Verb = Callable[[Act, Target, Options], str]


def brief(ticket: rulefiles.Ticket) -> str:
    """The rule files, the path gates and the instructions a worker's brief carries.

    Args:
        ticket: the checkout and the ticket's paths.

    Returns:
        The text.

    Raises:
        Refused: the recount finds a file the brief lacks.
    """
    text = rulefiles.write(ticket) + "\n" + totalroutes.instructions()
    lost = rulecount.missing(text, ticket)
    if lost:
        raise Refused(f"the recount finds rule files the brief lacks: {lost[:3]}")
    return text


def dispatch_next(act: Act, target: Target, options: Options) -> str:
    """The next piece of work, and its brief when a checkout is given.

    Args:
        act: the verb's world.
        target: the repository ("" for the project).
        options: ``want`` (the item meant), ``agent``, and for a brief
            ``checkout``, ``paths`` and ``home``.

    Returns:
        The item's reference, then its brief.
    """
    state = act.work()
    if cap := cap_of(act.owner):
        state = dataclasses.replace(state, cap=cap)
    item = act.controls.next_item(
        state, options.get("want", ""), options.get("agent", "")
    )
    if not options.get("checkout"):
        return item.ref
    ticket = rulefiles.Ticket(
        checkout=pathlib.Path(options["checkout"]),
        paths=options.get("paths", "").split(),
        home=pathlib.Path(options.get("home") or pathlib.Path.home()),
    )
    return f"{item.ref}\n{brief(ticket)}"


REFUSALS = (
    Refused,
    rulefiles.Refused,
    ticketreader.Refused,
    dispatchnext.Refused,
    rulecases.Refused,
)


def gate_first(
    name: str, verb: Verb, act: Act, target: Target, options: Options
) -> str:
    """Run a verb after the owner gate and the hold gate.

    Args:
        name: the verb's name, the one the hold gate reads.
        verb: the verb.
        act: the verb's world.
        target: what it acts on.
        options: its options.

    Returns:
        What the verb said.
    """
    gate(act, name, target.repo)
    return verb(act, target, options)


GATED: Mapping[str, Verb] = {
    "merge": functools.partial(actpull.gated_write, "merge"),
    "arm": functools.partial(actpull.gated_write, "arm"),
    "disarm": actpull.disarm,
    "undraft": functools.partial(actpull.gated_write, "undraft"),
    "review": actwrite.review,
    "label": actpull.label,
    "hold": actpull.hold,
    "unhold": actpull.unhold,
    "block": actpull.block,
    "override": actpull.override_stop,
    "ticket": actwrite.ticket,
    "ticket-edit": actwrite.ticket_edit,
    "close": actpull.close,
    "comment": actwrite.comment,
    "comment-edit": actwrite.comment_edit,
    "comment-delete": actwrite.comment_delete,
    "pr-create": actwrite.pr_create,
    "pr-edit": actwrite.pr_edit,
    "update-branch": actpull.update_branch,
    "rerun": actpull.rerun,
    "cancel": actpull.cancel,
    "dispatch-workflow": actpull.dispatch_workflow,
    "push": actgit.push,
    "dispatch-next": dispatch_next,
    "scratch-clean": actwrite.scratch_clean,
}
VERBS: Mapping[str, Verb] = {
    **{name: functools.partial(gate_first, name, verb) for name, verb in GATED.items()},
    "clean": actgit.clean,
    "ack": actwrite.ack,
}
