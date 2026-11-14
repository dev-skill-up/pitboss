"""What an act verb's decision is made from, read once (plan 6.1; keyword: act-verbs).

``read`` is called in the command's one read (``readworld``, through
``onepath.decisions``): it reads the owner's messages with no disposition and, for
the verbs whose decision turns on one, the fact from GitHub or the checkout. It
decides nothing; ``actdecide`` does.
"""

from typing import AbstractSet, Callable, Mapping, Sequence

from . import actcore, actfacts, actgit, actwrite, config
from .totaljson import members, name_at, records, text

Facts = Callable[[actcore.Act, actfacts.Asked], Sequence[actfacts.Check]]


def _size(act: actcore.Act, asked: actfacts.Asked) -> Sequence[actfacts.Check]:
    repo, options = asked.target.repo, asked.options
    lines = int(actcore.option(options, "max-lines"))
    ruled = bool(options.get("ruling"))
    return [actfacts.Size(repo=repo, lines=lines, p90=act.p90(repo), ruled=ruled)]


def _works_on(act: actcore.Act, repo: str) -> Sequence[tuple[int, AbstractSet[str]]]:
    # each open PR's number and the tickets it works on (the one parse)
    owned = config.make_repo(*repo.split("/", 1))
    return [
        (number, act.controls.works_on(*_said(each), owned))
        for each in act.hub.open_pulls(repo)
        if isinstance(number := each.get("number"), int)
    ]


def _said(row: Mapping[str, object]) -> tuple[str, str, str]:
    # a listing row's title, body and head branch
    return text(row.get("title")), text(row.get("body")), name_at(row, "head", "ref")


def _edit(act: actcore.Act, asked: actfacts.Asked) -> Sequence[actfacts.Check]:
    target = asked.target
    found = _works_on(act, target.repo)
    started = [number for number, names in found if target.name in names]
    starters = actfacts.Starters(ticket=target.name, pulls=started)
    return [starters, _form(act, asked, "body")]


def _form(act: actcore.Act, asked: actfacts.Asked, name: str) -> actfacts.Check:
    # a ticket body an option gives, as the ticket reader reads it
    body = actcore.option(asked.options, name)
    return actfacts.TicketForm(read=act.controls.items(body))


def _create(act: actcore.Act, asked: actfacts.Asked) -> Sequence[actfacts.Check]:
    return [_form(act, asked, "ticket")]


def _authored(act: actcore.Act, asked: actfacts.Asked) -> Sequence[actfacts.Check]:
    target = asked.target
    identifier = actcore.option(asked.options, "id")
    found = [
        each
        for each in records(actcore.timeline_of(act, target))
        if str(each.get("id")) == identifier
    ]
    identity = text(act.inputs(target.repo, target.number, {}, []).get("act_identity"))
    ours = bool(found) and members(found[0].get("user")).get("login") == identity
    keyed = actwrite.keyed(text(found[0].get("body"))) if ours else ""
    return [actfacts.Authored(ours=ours, keyed=keyed)]


def _push(act: actcore.Act, asked: actfacts.Asked) -> Sequence[actfacts.Check]:
    worktree, branch = actcore.options_of(asked.options, "worktree", "branch")
    asked_git = [
        ("symbolic-ref", "--quiet", "--short", "HEAD"),
        ("rev-parse", "--verify", "-q", "HEAD~1^{tree}"),
    ]
    (on, current), (has_parent, parent) = [
        actgit.tried(act, worktree, *each) for each in asked_git
    ]
    status, output = act.prepush()
    tree = actgit.said(act, worktree, "rev-parse", "HEAD^{tree}")
    return [
        actfacts.Pushing(
            current=current if on else "",
            assigned=branch,
            empty=has_parent and parent == tree,
            status=status,
            output=output,
        )
    ]


def _clean(act: actcore.Act, asked: actfacts.Asked) -> Sequence[actfacts.Check]:
    worktree = actcore.option(asked.options, "worktree")
    changes = bool(actgit.said(act, worktree, "status", "--porcelain"))
    left = actgit.said(
        act, worktree, "log", "--oneline", "--branches", "--not", "--remotes"
    )
    unpushed = left.splitlines()[0] if left else ""
    return [actfacts.Worktree(changes=changes, unpushed=unpushed)]


FACTS: Mapping[str, Facts] = {
    "ticket": _size,
    "ticket-edit": _edit,
    "pr-create": _create,
    "comment-edit": _authored,
    "comment-delete": _authored,
    "push": _push,
    "clean": _clean,
}


def read(act: actcore.Act, asked: actfacts.Asked) -> actfacts.ActRead:
    """Read what the verb a command asks for is decided from.

    Args:
        act: the verb's world.
        asked: the verb, its target and its options.

    Returns:
        The owner's messages with no disposition, the repositories the verb
        covers and the facts its own decision turns on.
    """
    owner = act.owner
    pending = [each for each in owner.messages if each not in owner.dispositions]
    where = asked.target.repo
    repos = act.repos if where in actcore.EVERY_REPOSITORY else [where]
    facts = FACTS.get(asked.verb)
    return actfacts.ActRead(
        verb=asked.verb,
        repos=repos,
        pending=pending,
        checks=facts(act, asked) if facts is not None else (),
    )
