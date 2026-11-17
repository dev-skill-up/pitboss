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
from typing import Callable, Literal, Mapping, assert_never

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


def applied_to_item(verb: gateverbs.ItemVerb) -> Verb:
    """What applies a verb of an item: a total match, so one with none is a type error.

    Args:
        verb: the verb.

    Returns:
        The function that runs it (P8, keyword: act-verbs).
    """
    match verb:
        case gateverbs.ItemVerb.MERGE:
            return functools.partial(actpull.gated_write, "merge")
        case gateverbs.ItemVerb.ARM:
            return functools.partial(actpull.gated_write, "arm")
        case gateverbs.ItemVerb.UNDRAFT:
            return functools.partial(actpull.gated_write, "undraft")
        case gateverbs.ItemVerb.OVERRIDE:
            return actpull.override_stop
        case gateverbs.ItemVerb.DISPATCH_NEXT:
            return dispatch_next
        case _:  # pragma: no cover
            assert_never(verb)


OwnFirst = Literal[
    gateverbs.OwnVerb.DISARM,
    gateverbs.OwnVerb.REVIEW,
    gateverbs.OwnVerb.LABEL,
    gateverbs.OwnVerb.HOLD,
    gateverbs.OwnVerb.UNHOLD,
    gateverbs.OwnVerb.BLOCK,
]


OwnSecond = Literal[
    gateverbs.OwnVerb.TICKET,
    gateverbs.OwnVerb.TICKET_EDIT,
    gateverbs.OwnVerb.CLOSE,
    gateverbs.OwnVerb.COMMENT,
    gateverbs.OwnVerb.COMMENT_EDIT,
    gateverbs.OwnVerb.COMMENT_DELETE,
]


OwnThird = Literal[
    gateverbs.OwnVerb.PR_CREATE,
    gateverbs.OwnVerb.PR_EDIT,
    gateverbs.OwnVerb.UPDATE_BRANCH,
    gateverbs.OwnVerb.RERUN,
    gateverbs.OwnVerb.CANCEL,
    gateverbs.OwnVerb.DISPATCH_WORKFLOW,
]


OwnFourth = Literal[
    gateverbs.OwnVerb.PUSH,
    gateverbs.OwnVerb.SCRATCH_CLEAN,
    gateverbs.OwnVerb.CLEAN,
    gateverbs.OwnVerb.ACK,
]


def applied_to_own_first(verb: OwnFirst) -> Verb:
    """What applies one of these own verbs: a total match.

    Args:
        verb: the verb.

    Returns:
        The function that runs it (P8, keyword: act-verbs).
    """
    match verb:
        case gateverbs.OwnVerb.DISARM:
            return actpull.disarm
        case gateverbs.OwnVerb.REVIEW:
            return actwrite.review
        case gateverbs.OwnVerb.LABEL:
            return actpull.label
        case gateverbs.OwnVerb.HOLD:
            return actpull.hold
        case gateverbs.OwnVerb.UNHOLD:
            return actpull.unhold
        case gateverbs.OwnVerb.BLOCK:
            return actpull.block
        case _:  # pragma: no cover
            assert_never(verb)


def applied_to_own_second(verb: OwnSecond) -> Verb:
    """What applies one of these own verbs: a total match.

    Args:
        verb: the verb.

    Returns:
        The function that runs it (P8, keyword: act-verbs).
    """
    match verb:
        case gateverbs.OwnVerb.TICKET:
            return actwrite.ticket
        case gateverbs.OwnVerb.TICKET_EDIT:
            return actwrite.ticket_edit
        case gateverbs.OwnVerb.CLOSE:
            return actpull.close
        case gateverbs.OwnVerb.COMMENT:
            return actwrite.comment
        case gateverbs.OwnVerb.COMMENT_EDIT:
            return actwrite.comment_edit
        case gateverbs.OwnVerb.COMMENT_DELETE:
            return actwrite.comment_delete
        case _:  # pragma: no cover
            assert_never(verb)


def applied_to_own_third(verb: OwnThird) -> Verb:
    """What applies one of these own verbs: a total match.

    Args:
        verb: the verb.

    Returns:
        The function that runs it (P8, keyword: act-verbs).
    """
    match verb:
        case gateverbs.OwnVerb.PR_CREATE:
            return actwrite.pr_create
        case gateverbs.OwnVerb.PR_EDIT:
            return actwrite.pr_edit
        case gateverbs.OwnVerb.UPDATE_BRANCH:
            return actpull.update_branch
        case gateverbs.OwnVerb.RERUN:
            return actpull.rerun
        case gateverbs.OwnVerb.CANCEL:
            return actpull.cancel
        case gateverbs.OwnVerb.DISPATCH_WORKFLOW:
            return actpull.dispatch_workflow
        case _:  # pragma: no cover
            assert_never(verb)


def applied_to_own_fourth(verb: OwnFourth) -> Verb:
    """What applies one of these own verbs: a total match.

    Args:
        verb: the verb.

    Returns:
        The function that runs it (P8, keyword: act-verbs).
    """
    match verb:
        case gateverbs.OwnVerb.PUSH:
            return actgit.push
        case gateverbs.OwnVerb.SCRATCH_CLEAN:
            return actwrite.scratch_clean
        case gateverbs.OwnVerb.CLEAN:
            return actgit.clean
        case gateverbs.OwnVerb.ACK:
            return actwrite.ack
        case _:  # pragma: no cover
            assert_never(verb)


def applied_to_own(verb: gateverbs.OwnVerb) -> Verb:
    """What applies a verb of its own: each group's match is total, and so is this.

    Args:
        verb: the verb.

    Returns:
        The function that runs it (P8, keyword: act-verbs).
    """
    match verb:
        case (
            gateverbs.OwnVerb.DISARM
            | gateverbs.OwnVerb.REVIEW
            | gateverbs.OwnVerb.LABEL
            | gateverbs.OwnVerb.HOLD
            | gateverbs.OwnVerb.UNHOLD
            | gateverbs.OwnVerb.BLOCK
        ):
            return applied_to_own_first(verb)
        case (
            gateverbs.OwnVerb.TICKET
            | gateverbs.OwnVerb.TICKET_EDIT
            | gateverbs.OwnVerb.CLOSE
            | gateverbs.OwnVerb.COMMENT
            | gateverbs.OwnVerb.COMMENT_EDIT
            | gateverbs.OwnVerb.COMMENT_DELETE
        ):
            return applied_to_own_second(verb)
        case (
            gateverbs.OwnVerb.PR_CREATE
            | gateverbs.OwnVerb.PR_EDIT
            | gateverbs.OwnVerb.UPDATE_BRANCH
            | gateverbs.OwnVerb.RERUN
            | gateverbs.OwnVerb.CANCEL
            | gateverbs.OwnVerb.DISPATCH_WORKFLOW
        ):
            return applied_to_own_third(verb)
        case (
            gateverbs.OwnVerb.PUSH
            | gateverbs.OwnVerb.SCRATCH_CLEAN
            | gateverbs.OwnVerb.CLEAN
            | gateverbs.OwnVerb.ACK
        ):
            return applied_to_own_fourth(verb)
        case _:  # pragma: no cover
            assert_never(verb)


VERBS: Mapping[str, Verb] = {
    **{each.value: applied_to_item(each) for each in gateverbs.ItemVerb},
    **{each.value: applied_to_own(each) for each in gateverbs.OwnVerb},
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
    """
    verb = gateverbs.verb_of(asked.verb)
    found = gateverbs.lookup(act.questions.decided(asked), verb, asked.target.name)
    if _stands(verb, found, asked):
        said = _said(found)
        if verb is gateverbs.ItemVerb.OVERRIDE:
            stop = asked.options.get("stop", "")[:60]
            said = f"not an overridable stop of this item's decision: {stop!r}; {said}"
        return f"{render.NOT_DONE}: {asked.verb} {asked.target.name}: {said}"
    return table[asked.verb](act, asked.target, asked.options)
