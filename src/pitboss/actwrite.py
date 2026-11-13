"""The verbs that write the texts the checker reads (keyword: act-verbs).

``act review`` writes the one review form the verdict reads (``review_text``), so a
hand-typed ``Plan: ok`` has no way to be written; ``act ticket`` writes the one
ticket form the reader takes; ``act pr-create`` and ``act pr-edit`` check the body
rows first; ``act comment`` carries no review or act line; a comment is edited or
deleted only when it is pitboss's own evidence. A started ticket (a PR closes it)
gets nothing added.
"""

import re
from typing import Callable, Mapping, Sequence

from . import actcore, bodydigest, pullobject, totalbody, totalreview
from .actcore import (
    disarm_first,
    head_now,
    options_of,
    pull_of,
    put,
    repo_write,
    timeline_of,
)
from .actstands import Said, Stands, Why
from .plansection import plan_section
from .ticketreader import written
from .totaljson import JsonMap, members, records, text
from .textparts import mentions_any

GRADES = ("approved", "changes needed")
GRADE_KEY = re.compile(
    r"^\W*(verdict|reviewed|plan|execution|body|ticket|pitboss-act)\b\W*:?", re.I
)
FIXES = re.compile(r"Fixes (\S+/\S+)?#\d+\n")
SCRATCH = ("bats-lang/relock-scratch",)


def review_text(
    pull: JsonMap, grades: Sequence[str], findings: str, tickets: JsonMap
) -> str:
    """The review ``act review`` writes.

    Args:
        pull: the PR as read.
        grades: the Plan, Execution and verdict grades.
        findings: what the review found.
        tickets: each ticket the body closes, as read.

    Returns:
        The head, the grades, the verdict and the digests of the body, its Plan and
        each ticket, then the findings.
    """
    body = text(pull.get("body"))
    section = plan_section(body)
    lines = [
        f"Reviewed: {actcore.head_of(pull)}",
        f"Plan: {grades[0]}",
        f"Execution: {grades[1]}",
        f"Verdict: {grades[2]}",
        f"Body: {totalreview.digest_of(body)}",
        *([] if section is None else [f"Plan-digest: {bodydigest.digest(section)}"]),
        *totalreview.ticket_lines(pullobject.tickets_of(tickets)),
    ]
    return "\n".join(lines) + f"\n\n{findings}"


def _plain(words: str) -> None:
    bad = [line for line in words.splitlines() if GRADE_KEY.match(line)]
    if bad:
        raise actcore.Refused(
            f"a line starts with a review or act key: {bad[0][:40]!r}; use the verb"
        )


def review(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Post a review in the one form the verdict reads.

    Args:
        act: the verb's world.
        target: the PR.
        options: ``plan``, ``execution``, ``verdict`` (each approved or changes
            needed) and ``findings``.

    Returns:
        The review's text.

    Raises:
        actcore.Refused: a grade in another form, or findings that carry a grade line.
    """
    grades = [text(options.get(each)) for each in ("plan", "execution", "verdict")]
    if any(each not in GRADES for each in grades):
        raise actcore.Refused("a grade is approved or changes needed")
    findings = actcore.option(options, "findings")
    _plain(findings)
    pull = pull_of(act, target)
    tickets = members(act.inputs(target.repo, target.number, pull, []).get("tickets"))
    words = review_text(pull, grades, findings, tickets)
    put(act, target, "comment", {"body": words})
    return words


def _size(act: actcore.Act, repo: str, options: actcore.Options) -> int | Stands:
    # the ticket's Max-lines; over the repository's p90 only with a ruling
    size = int(actcore.option(options, "max-lines"))
    most = act.p90(repo)
    if size > most and not options.get("ruling"):
        line = f"Max-lines {size} is over {repo}'s p90 {most}: a ruling names it"
        return Stands(why=Why.OVER_P90, line=line)
    return size


def ticket(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> Said:
    """File a ticket in the one form the ticket reader takes.

    It is refused with no item or path, or with a size over the repository's p90
    and no ruling.

    Args:
        act: the verb's world.
        target: the repository.
        options: ``title``, ``done-when`` (items, one per line), ``paths``,
            ``max-lines``, ``priority`` and ``ruling`` (for a size over the p90).

    Returns:
        The ticket's number.
    """
    items = actcore.option(options, "done-when").splitlines()
    done_when = [each for each in items if each.strip()]
    paths = actcore.option(options, "paths").split()
    size = _size(act, target.repo, options)
    if isinstance(size, Stands):
        return size
    body = written(done_when, paths, size, actcore.option(options, "priority"))
    fields = {"title": actcore.option(options, "title"), "body": body, "labels": ""}
    return repo_write(act, target.repo, "issue", fields)


def _bodies(act: actcore.Act, repo: str) -> Sequence[tuple[int, str]]:
    # each open PR's number and body
    pulls = act.hub.open_pulls(repo)
    found = [(each.get("number"), text(each.get("body"))) for each in pulls]
    return [(number, body) for number, body in found if isinstance(number, int)]


def _place(target: actcore.Target) -> tuple[str, int]:
    return target.repo, target.number


def ticket_edit(
    act: actcore.Act, target: actcore.Target, options: actcore.Options
) -> Said:
    """Change a ticket that no PR has started.

    Args:
        act: the verb's world.
        target: the ticket.
        options: ``body``: the new body, in the ticket form.

    Returns:
        What was done, or that a PR closes the ticket, so a worker started it.
    """
    started = act.controls.started(_bodies(act, target.repo), *_place(target))
    if started:
        line = f"PR #{started[0]} closes {target.name}, so a worker started:"
        line += " a started ticket gets nothing added (file a new ticket)"
        return Stands(why=Why.STARTED, line=line)
    body = actcore.option(options, "body")
    act.controls.items(body)
    put(act, target, "issue-edit", {"body": body})
    return f"ticket-edit {target.name}"


def comment(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Post a plain comment (no review or act line).

    Args:
        act: the verb's world.
        target: the PR or issue.
        options: ``body``.

    Returns:
        What GitHub answered.
    """
    body = actcore.option(options, "body")
    _plain(body)
    return put(act, target, "comment", {"body": body})


def _own_comment(
    act: actcore.Act, target: actcore.Target, identifier: str
) -> actcore.Stood:
    found = [
        each
        for each in records(timeline_of(act, target))
        if str(each.get("id")) == identifier
    ]
    identity = text(act.inputs(target.repo, target.number, {}, []).get("act_identity"))
    if not found or members(found[0].get("user")).get("login") != identity:
        return [Stands(why=Why.NOT_OURS, line="not a comment pitboss act posted")]
    _plain(text(found[0].get("body")))
    return []


def comment_edit(
    act: actcore.Act, target: actcore.Target, options: actcore.Options
) -> Said:
    """Replace the text of pitboss's own evidence comment (never a review or record).

    Args:
        act: the verb's world.
        target: the PR or issue.
        options: ``id`` and ``body``.

    Returns:
        What was done.
    """
    identifier, body = options_of(options, "id", "body")
    if stood := _own_comment(act, target, identifier):
        return stood[0]
    _plain(body)
    put(act, target, "comment-edit", {"id": identifier, "body": body})
    return f"comment-edit {identifier}"


def comment_delete(
    act: actcore.Act, target: actcore.Target, options: actcore.Options
) -> Said:
    """Delete pitboss's own evidence comment (never a review or record).

    Args:
        act: the verb's world.
        target: the PR or issue.
        options: ``id``.

    Returns:
        What was done.
    """
    identifier = actcore.option(options, "id")
    if stood := _own_comment(act, target, identifier):
        return stood[0]
    put(act, target, "comment-delete", {"id": identifier})
    return f"comment-delete {identifier}"


def _body_rows(body: str, head: str, skip: Sequence[str]) -> None:
    if not FIXES.match(body):
        raise actcore.Refused("the body's first line is not `Fixes #N`")
    found = [
        each
        for each in totalbody.body_findings(body, head)
        if not mentions_any(each, skip)
    ]
    if found:
        raise actcore.Refused(found[0])


def pr_create(
    act: actcore.Act, target: actcore.Target, options: actcore.Options
) -> str:
    """Open a PR whose body is in its form, for a ticket in its form.

    Args:
        act: the verb's world.
        target: the repository.
        options: ``head`` (the branch), ``title``, ``body`` and ``ticket`` (its body).

    Returns:
        The PR's number.
    """
    act.controls.items(actcore.option(options, "ticket"))
    body = actcore.option(options, "body")
    _body_rows(body, "", ("Head", "blocked by"))
    fields = {
        "head": actcore.option(options, "head"),
        "title": actcore.option(options, "title"),
        "body": body,
    }
    return repo_write(act, target.repo, "pr", fields)


def pr_edit(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Change a PR's title or body; an armed PR is disarmed first.

    Args:
        act: the verb's world.
        target: the PR.
        options: ``title`` and/or ``body``.

    Returns:
        What was done.
    """
    fields = {key: options[key] for key in ("title", "body") if options.get(key)}
    if "body" in fields:
        _body_rows(
            fields["body"],
            head_now(act, target),
            ("blocked by",),
        )
    disarm_first(act, target, "the body or the title changes")
    put(act, target, "pr-edit", fields)
    return f"pr-edit {target.name}"


def scratch_clean(
    act: actcore.Act, target: actcore.Target, options: actcore.Options
) -> str:
    """Delete a scratch branch and close its PR, in a scratch repository only.

    Args:
        act: the verb's world.
        target: the scratch repository and the PR (0 for none).
        options: ``branch``.

    Returns:
        What was done.

    Raises:
        actcore.Refused: not a scratch repository.
    """
    if target.repo not in SCRATCH:
        raise actcore.Refused(f"{target.repo} is not a scratch repository")
    if branch := options.get("branch"):
        whole = actcore.Target(repo=target.repo)
        put(act, whole, "branch-delete", {"branch": branch})
    if target.number:
        put(act, target, "pr-close")
    return f"scratch-clean {target.repo}"


def ack(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Give an owner message its disposition, making what it names.

    Args:
        act: the verb's world.
        target: the repository a hold or a note goes to ("all" for a hold of all).
        options: ``message``, ``kind`` (hold, cap, ruling, none) and what the
            kind needs: ``scope`` (hold), ``cap`` (cap), ``reason`` (a URL or #N
            for a ruling, a reason for none) and ``quote`` (none).

    Returns:
        The disposition.

    Raises:
        actcore.Refused: a kind in no row, or what it needs is missing.
    """
    message, kind = options_of(options, "message", "kind")
    if kind not in ACKS:
        raise actcore.Refused(f"ack is {', '.join(ACKS)}")
    ACKS[kind](act, target, options)
    act.owner.dispositions[message] = kind
    return f"ack {message} {kind}"


def _note(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> None:
    quote, reason = text(options.get("quote")), text(options.get("reason"))
    if not quote or len(reason) < 10:
        raise actcore.Refused("ack none quotes the message and gives a reason")
    repo = act.repos[0] if target.repo == "all" else target.repo
    fields = {
        "title": f"owner message {options['message']}: no action",
        "body": f"> {quote}\n\nreason: {reason}",
        "labels": actcore.ACK_LABEL,
    }
    repo_write(act, repo, "issue", fields)


def _hold(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> None:
    scope = actcore.option(options, "scope")
    actcore.make_hold(act, target.repo, scope, options["message"])


def _cap(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> None:
    act.owner.caps[options["message"]] = int(actcore.option(options, "cap"))


def _ruling(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> None:
    if not text(options.get("reason")).startswith(("http", "#")):
        raise actcore.Refused("ack ruling names the ruling (a URL or #N)")


ACKS: Mapping[str, Callable[[actcore.Act, actcore.Target, actcore.Options], None]] = {
    "hold": _hold,
    "cap": _cap,
    "ruling": _ruling,
    "none": _note,
}
