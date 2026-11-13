"""The verbs of ``pitboss act``, by name (keyword: act-verbs).

``VERBS`` is the one table: the command line, the route table's verbs and the
completeness test all read it. Every verb but ``ack`` and ``clean`` passes the
owner gate and the hold gate first (``gate_first``). ``dispatch-next`` is here: it
answers the one next piece of work, and for a ticket with a checkout it writes the
brief (every rule file on the ticket's paths, the verdict's gates on them, and the
instructions of the route table), refused when the recount finds a file missing.
"""

import functools
import pathlib
from typing import Callable, Mapping

from . import (
    actgit,
    actpull,
    actwrite,
    answer,
    gateverbs,
    render,
    rulecases,
    rulecount,
    rulefiles,
    ticketreader,
    actrules,
)
from .actcore import Act, Options, Refused, Target, gate
from .actstands import Said

Verb = Callable[[Act, Target, Options], Said]


def brief(ticket: rulefiles.Ticket) -> str:
    """The rule files, the path gates and the instructions a worker's brief carries.

    Args:
        ticket: the checkout and the ticket's paths.

    Returns:
        The text.

    Raises:
        Refused: the recount finds a file the brief lacks.
    """
    text = rulefiles.write(ticket) + "\n" + actrules.instructions()
    lost = rulecount.missing(text, ticket)
    if lost:
        raise Refused(f"the recount finds rule files the brief lacks: {lost[:3]}")
    return text


def dispatch_next(act: Act, target: Target, options: Options) -> str:
    """The next piece of work, and its brief when a checkout is given.

    The head of the one order of ``slots next`` (keyword: one-path): ``want``
    names the item the caller means, which must be it.

    Args:
        act: the verb's world.
        target: the repository ("" for the project).
        options: ``want`` (the item meant), and for a brief ``checkout``,
            ``paths`` and ``home``.

    Returns:
        The item's reference, then its brief; or, when the named item is not the
        head of the order, the decision that stands; or the ``NOT ENOUGH WORK`` line.
    """
    want = options.get("want", "")
    verb = gateverbs.Verb.DISPATCH_NEXT
    given = gateverbs.lookup(act.questions.decided(), verb, want)
    said = render.dispatch(given)[0]
    if not isinstance(given, answer.Decision):
        return said
    if want and want != given.item:
        return f"{render.NOT_DONE}: dispatch-next {want}: {render.standing(given)}"
    return f"{said}\n{brief(_ticket(options))}" if options.get("checkout") else said


def _ticket(options: Options) -> rulefiles.Ticket:
    # the checkout a brief is made from
    home = options.get("home")
    return rulefiles.Ticket(
        checkout=pathlib.Path(options["checkout"]),
        paths=options.get("paths", "").split(),
        home=pathlib.Path(home) if home else pathlib.Path.home(),
    )


REFUSALS = (
    Refused,
    rulefiles.Refused,
    ticketreader.Refused,
    rulecases.Refused,
)


def gate_first(
    gated: tuple[str, Verb], act: Act, target: Target, options: Options
) -> Said:
    """Run a verb after the owner gate and the hold gate.

    Args:
        gated: the verb's name, the one the hold gate reads, and the verb.
        act: the verb's world.
        target: what it acts on.
        options: its options.

    Returns:
        What the verb said, or what stands instead of it.
    """
    name, verb = gated
    stood = gate(act, name, target.repo)
    return stood[0] if stood else verb(act, target, options)


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
    **{
        name: functools.partial(gate_first, (name, verb))
        for name, verb in GATED.items()
    },
    "clean": actgit.clean,
    "ack": actwrite.ack,
}
