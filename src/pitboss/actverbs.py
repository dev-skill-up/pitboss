"""The verbs of ``pitboss act``, by name (keyword: act-verbs).

``VERBS`` is the one table: the command line, the route table's verbs and the
completeness test all read it. ``dispatch-next`` is here: it answers the one
next piece of work, and for a ticket with a checkout it writes the brief (every
rule file on the ticket's paths, the verdict's gates on them, and the
instructions of the route table), refused when the recount finds a file missing.
"""

import dataclasses
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
    gate(act, "dispatch-next", target.repo)
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
VERBS: Mapping[str, Verb] = {
    "merge": actpull.merge,
    "arm": actpull.arm,
    "disarm": actpull.disarm,
    "undraft": actpull.undraft,
    "review": actwrite.review,
    "label": actpull.label,
    "hold": actpull.hold,
    "unhold": actpull.unhold,
    "block": actpull.block,
    "override": actpull.override,
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
    "clean": actgit.clean,
    "dispatch-next": dispatch_next,
    "ack": actwrite.ack,
    "scratch-clean": actwrite.scratch_clean,
}
