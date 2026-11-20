"""What every ``act`` verb looks up in the decisions (keyword: gate, act-verbs).

The one-path plan, P8: every verb looks its answer up in the one ``Decided`` its
command's read gave (``lookup``): ``NotDone`` when an owner message, a hold or the
fact its own decision turns on stands (``actdecide``); merge, arm and undraft run
only when the item's decision is their own, an override lifts only the stop the
decision answers, and ``dispatch-next`` is the head of the order. The decisions
are made by ``gate``, ``decide`` and ``actdecide``; nothing here reads or decides.
"""

import enum
from typing import Mapping, assert_never

from . import answer, project


class ItemVerb(enum.Enum):
    """An act verb whose answer is a decision of the order (``lookup``).

    Attributes:
        MERGE: merge a PR whose decision is the merge.
        ARM: arm auto-merge on a PR whose decision is the merge.
        UNDRAFT: mark ready a PR whose decision is the undraft.
        OVERRIDE: lift the stop the item's decision answers.
        DISPATCH_NEXT: the head of the order, and its brief.
    """

    MERGE = "merge"
    ARM = "arm"
    UNDRAFT = "undraft"
    OVERRIDE = "override"
    DISPATCH_NEXT = "dispatch-next"


class OwnVerb(enum.Enum):
    """An act verb with no decision of its own: ``NotDone`` or nothing stands.

    Attributes:
        DISARM: take auto-merge off a PR.
        REVIEW: post a review in the one form the verdict reads.
        LABEL: add or take off a label.
        HOLD: make a hold.
        UNHOLD: end a hold.
        BLOCK: record what a PR waits for.
        TICKET: file a ticket in the reader's form.
        TICKET_EDIT: change a ticket no PR started.
        CLOSE: close a PR or an issue.
        COMMENT: post a plain comment.
        COMMENT_EDIT: change pitboss's own evidence comment.
        COMMENT_DELETE: delete pitboss's own evidence comment.
        PR_CREATE: open a PR whose body is in its form.
        PR_EDIT: change a PR's title or body.
        UPDATE_BRANCH: merge the base into a PR's branch.
        RERUN: run a PR's failed jobs again.
        CANCEL: cancel a run.
        DISPATCH_WORKFLOW: start a workflow.
        PUSH: push a worktree to its assigned branch.
        SCRATCH_CLEAN: close a scratch PR whose run finished.
        CLEAN: remove a finished worktree.
        ACK: record an owner message's disposition.
    """

    DISARM = "disarm"
    REVIEW = "review"
    LABEL = "label"
    HOLD = "hold"
    UNHOLD = "unhold"
    BLOCK = "block"
    TICKET = "ticket"
    TICKET_EDIT = "ticket-edit"
    CLOSE = "close"
    COMMENT = "comment"
    COMMENT_EDIT = "comment-edit"
    COMMENT_DELETE = "comment-delete"
    PR_CREATE = "pr-create"
    PR_EDIT = "pr-edit"
    UPDATE_BRANCH = "update-branch"
    RERUN = "rerun"
    CANCEL = "cancel"
    DISPATCH_WORKFLOW = "dispatch-workflow"
    PUSH = "push"
    SCRATCH_CLEAN = "scratch-clean"
    CLEAN = "clean"
    ACK = "ack"


Verb = ItemVerb | OwnVerb  # an act verb, by its word: each looks its answer up
ON_ITEMS = frozenset(ItemVerb) - {ItemVerb.DISPATCH_NEXT}  # merge, arm, undraft, ...
# the verbs with no mode of their own (``mode.ActOn``)
ACTED_ON = frozenset(OwnVerb)
ITEM_WORDS = frozenset(each.value for each in ItemVerb)
Standing = answer.Standing
Looked = answer.Standing | answer.Acting  # what a verb finds stands


CARRIED: Mapping[Verb, answer.Carried] = {  # the step each gated verb carries out
    ItemVerb.MERGE: answer.Carried.MERGE,
    ItemVerb.ARM: answer.Carried.MERGE,
    ItemVerb.UNDRAFT: answer.Carried.UNDRAFT,
}


def verb_of(word: str) -> Verb:
    """The act verb a word names.

    Args:
        word: the verb's word, one of ``actverbs.VERBS``.

    Returns:
        The verb (``OwnVerb``'s ``ValueError`` for a word that names none).
    """
    return ItemVerb(word) if word in ITEM_WORDS else OwnVerb(word)


def lookup(decided: answer.Decided, verb: Verb, item: str) -> Looked:
    """The decision that stands for a verb on an item (P8): act's one lookup.

    Args:
        decided: the decisions of the world the verb read.
        verb: the verb.
        item: the item it names (empty for ``dispatch-next`` of any).

    Returns:
        What stands instead of the verb (``NotDone``) when anything does; else the
        item's decision for a verb on an item (the head of the order when the item
        has none), the head of the order for ``dispatch-next``, None for any
        other verb.
    """
    match verb:
        case ItemVerb.DISPATCH_NEXT:
            found: Looked = project.dispatch_next(decided)
        case ItemVerb():
            found = decided.by_item.get(item) or project.dispatch_next(decided)
        case OwnVerb():
            found = None
        case _:  # pragma: no cover
            assert_never(verb)
    stood = decided.acting
    return stood if isinstance(stood, answer.NotDone) else found


def overridable(found: Looked, item: str, line: str) -> bool:
    """Whether ``act override`` may lift a stop: the item's decision answers it.

    Args:
        found: the decision that stands (``lookup``).
        item: the item the override names.
        line: the stop line.

    Returns:
        True when the decision is the route of that stop and the route is one an
        override lifts.
    """
    if not isinstance(found, answer.Decision) or found.item != item:
        return False
    return line != "" and found.lifts == line


def allows(verb: Verb, found: Looked, item: str) -> bool:
    """Whether an act verb runs: the decision that stands is the verb's own.

    Args:
        verb: ``MERGE``, ``ARM`` or ``UNDRAFT``.
        found: the decision that stands (``lookup``).
        item: the item the verb names.

    Returns:
        True when it is the item's decision and the step the verb carries out.
    """
    if not isinstance(found, answer.Decision) or found.item != item:
        return False
    wanted = CARRIED.get(verb, answer.Carried.NOTHING)
    return wanted is not answer.Carried.NOTHING and found.carried is wanted
