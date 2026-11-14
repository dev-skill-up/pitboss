"""The verbs of ``pitboss act``, by name (keyword: act-verbs).

``VERBS`` is the one table: the command line, the route table's verbs and the
completeness test all read it. ``run`` is the one way a verb runs: it looks the
verb's answer up in the decisions of the command's one read (``gateverbs.lookup``,
P8) and applies the verb only when nothing stands instead; an owner message, a hold
and the fact a verb's own decision turns on are ``decide``'s (``actdecide``).
``dispatch-next`` is here: it answers the one next piece of work, and for a ticket
with a checkout it writes the brief (every rule file on the ticket's paths, the
verdict's gates on them, and the instructions of the route table), refused when
the recount finds a file missing.
"""

import functools
import pathlib
from typing import Callable, Mapping

from . import (
    actfacts,
    actgit,
    actpull,
    actwrite,
    answer,
    gateverbs,
    project,
    render,
    rulecases,
    rulecount,
    rulefiles,
    actrules,
)
from .actcore import Act, Options, Refused, Target

Verb = Callable[[Act, Target, Options], str]
Asked = actfacts.Asked
# the verbs that run only when the item's decision is their own step
GATED_ON_ITEM = frozenset(
    {gateverbs.ItemVerb.MERGE, gateverbs.ItemVerb.ARM, gateverbs.ItemVerb.UNDRAFT}
)


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
    given = head(act, target, options)
    said = render.dispatch(given)[0]
    if not isinstance(given, answer.Decision):
        return said
    if want and want != given.item:
        return f"{render.NOT_DONE}: dispatch-next {want}: {render.standing(given)}"
    return f"{said}\n{brief(_ticket(options))}" if options.get("checkout") else said


def head(act: Act, target: Target, options: Options) -> answer.Standing:
    """The head of the order, in the decisions of ``dispatch-next``'s one read.

    Args:
        act: the verb's world.
        target: the repository ("" for the project).
        options: the verb's options.

    Returns:
        The first decision, or that there is no work.
    """
    asked = actfacts.Asked(verb="dispatch-next", target=target, options=options)
    decided = act.questions.decided(asked)
    return project.dispatch_next(decided)


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
    rulecases.Refused,
)


VERBS: Mapping[str, Verb] = {
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
    "clean": actgit.clean,
    "ack": actwrite.ack,
}


def _said(found: gateverbs.Looked) -> str:
    # what stands instead of a verb (P8)
    match found:
        case answer.NotDone():
            return found.line
        case answer.Decision() | answer.NotEnoughWork():
            return render.standing(found)
        case None:  # pragma: no cover
            return ""


def _stands(verb: gateverbs.Verb, found: gateverbs.Looked, asked: Asked) -> bool:
    # whether the verb's answer is another than doing it
    item, options = asked.target.name, asked.options
    if isinstance(found, answer.NotDone):
        return True
    if verb in GATED_ON_ITEM:
        return not gateverbs.allows(verb, found, item)
    if verb is gateverbs.ItemVerb.OVERRIDE:
        return not gateverbs.overridable(found, item, options.get("stop", ""))
    return False


def run(act: Act, asked: Asked, table: Mapping[str, Verb]) -> str:
    """Run one verb: look its answer up in the decisions, then apply it (P8).

    Args:
        act: the verb's world.
        asked: the verb, its target and its options.
        table: what applies each verb (``VERBS``).

    Returns:
        What it did; or the ``NOT DONE`` line of what stands instead of it.

    Raises:
        Refused: no such verb.
    """
    if asked.verb not in table:
        raise Refused(f"no verb {asked.verb!r}: {', '.join(sorted(table))}")
    verb = gateverbs.verb_of(asked.verb)
    found = gateverbs.lookup(act.questions.decided(asked), verb, asked.target.name)
    if _stands(verb, found, asked):
        said = _said(found)
        if verb is gateverbs.ItemVerb.OVERRIDE:
            stop = asked.options.get("stop", "")[:60]
            said = f"not an overridable stop of this item's decision: {stop!r}; {said}"
        return f"{render.NOT_DONE}: {asked.verb} {asked.target.name}: {said}"
    return table[asked.verb](act, asked.target, asked.options)
