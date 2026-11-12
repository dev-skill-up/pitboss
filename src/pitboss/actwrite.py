"""The verbs that write the texts the checker reads (keyword: act-verbs).

``act review`` writes the one review form the verdict reads (``review_text``), so a
hand-typed ``Plan: ok`` has no way to be written; ``act ticket`` writes the one
ticket form the reader takes; ``act pr-create`` and ``act pr-edit`` check the body
rows first; ``act comment`` carries no review or act line; a comment is edited or
deleted only when it is pitboss's own evidence. A started ticket (a PR closes it)
gets nothing added.
"""

import re
from typing import Sequence

from . import bodydigest, totalbody, totalreview
from .actcore import (
    ACK_LABEL,
    Act,
    Change,
    Options,
    Refused,
    Target,
    gate,
    head_of,
    option,
)
from .actpull import make_hold
from .ticketreader import written
from .totaljson import JsonMap, mapping, records, text

GRADES = ("approved", "changes needed")
GRADE_KEY = re.compile(
    r"^\W*(verdict|reviewed|plan|execution|body|ticket|pitboss-act)\b\W*:?", re.I
)
FIXES = re.compile(r"Fixes (\S+/\S+)?#\d+\n")
SCRATCH = ("bats-lang/relock-scratch",)
ACKS = ("hold", "cap", "ruling", "none")


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
    body = pull.get("body")
    section = totalreview.plan_section(body)
    lines = [
        f"Reviewed: {head_of(pull)}",
        f"Plan: {grades[0]}",
        f"Execution: {grades[1]}",
        f"Verdict: {grades[2]}",
        f"Body: {totalreview.digest_of(body)}",
        *([] if section is None else [f"Plan-digest: {bodydigest.digest(section)}"]),
        *totalreview.ticket_lines(tickets),
    ]
    return "\n".join(lines) + f"\n\n{findings}"


def _plain(words: str) -> None:
    bad = [line for line in words.splitlines() if GRADE_KEY.match(line)]
    if bad:
        raise Refused(
            f"a line starts with a review or act key: {bad[0][:40]!r}; use the verb"
        )


def review(act: Act, target: Target, options: Options) -> str:
    """Post a review in the one form the verdict reads.

    Args:
        act: the verb's world.
        target: the PR.
        options: ``plan``, ``execution``, ``verdict`` (each approved or changes
            needed) and ``findings``.

    Returns:
        The review's text.

    Raises:
        Refused: a grade in another form, or findings that carry a grade line.
    """
    gate(act, "review", target.repo)
    grades = [text(options.get(each)) for each in ("plan", "execution", "verdict")]
    if any(each not in GRADES for each in grades):
        raise Refused("a grade is approved or changes needed")
    findings = option(options, "findings")
    _plain(findings)
    pull = act.hub.pull(target.repo, target.number)
    tickets = mapping(act.inputs(target.repo, target.number, pull, []).get("tickets"))
    words = review_text(pull, grades, findings, tickets)
    act.hub.write(
        Change(
            kind="comment",
            repo=target.repo,
            number=target.number,
            fields={"body": words},
        )
    )
    return words


def ticket(act: Act, target: Target, options: Options) -> str:
    """File a ticket in the one form the ticket reader takes.

    Args:
        act: the verb's world.
        target: the repository.
        options: ``title``, ``done-when`` (items, one per line), ``paths``,
            ``max-lines``, ``priority`` and ``ruling`` (for a size over the p90).

    Returns:
        The ticket's number.

    Raises:
        Refused: no item or path, or a size over the repository's p90 with no ruling.
    """
    gate(act, "ticket", target.repo)
    done_when = [
        each for each in option(options, "done-when").splitlines() if each.strip()
    ]
    paths = option(options, "paths").split()
    size = int(option(options, "max-lines"))
    most = act.p90.get(target.repo, 0)
    if size > most and not options.get("ruling"):
        raise Refused(
            f"Max-lines {size} is over {target.repo}'s p90 {most}: a ruling names it"
        )
    body = written(done_when, paths, size, option(options, "priority"))
    fields = {"title": option(options, "title"), "body": body, "labels": ""}
    return act.hub.write(Change(kind="issue", repo=target.repo, fields=fields))


def ticket_edit(act: Act, target: Target, options: Options) -> str:
    """Change a ticket that no PR has started.

    Args:
        act: the verb's world.
        target: the ticket.
        options: ``body``: the new body, in the ticket form.

    Returns:
        What was done.

    Raises:
        Refused: a PR closes the ticket, so a worker started it.
    """
    gate(act, "ticket-edit", target.repo)
    bodies = [
        (each.get("number"), each.get("body")) for each in act.hub.pulls(target.repo)
    ]
    started = act.controls.started(
        [(n, text(b)) for n, b in bodies if isinstance(n, int)],
        target.repo,
        target.number,
    )
    if started:
        raise Refused(
            f"PR #{started[0]} closes {target.repo}#{target.number}, so a worker"
            " started: a started ticket gets nothing added (file a new ticket)"
        )
    body = option(options, "body")
    act.controls.items(body)
    act.hub.write(
        Change(
            kind="issue-edit",
            repo=target.repo,
            number=target.number,
            fields={"body": body},
        )
    )
    return f"ticket-edit {target.repo}#{target.number}"


def comment(act: Act, target: Target, options: Options) -> str:
    """Post a plain comment (no review or act line).

    Args:
        act: the verb's world.
        target: the PR or issue.
        options: ``body``.

    Returns:
        What GitHub answered.
    """
    gate(act, "comment", target.repo)
    body = option(options, "body")
    _plain(body)
    return act.hub.write(
        Change(
            kind="comment",
            repo=target.repo,
            number=target.number,
            fields={"body": body},
        )
    )


def _own_comment(act: Act, target: Target, identifier: str) -> None:
    found = [
        each
        for each in records(act.hub.timeline(target.repo, target.number))
        if str(each.get("id")) == identifier
    ]
    identity = text(act.inputs(target.repo, target.number, {}, []).get("act_identity"))
    if not found or mapping(found[0].get("user")).get("login") != identity:
        raise Refused("not a comment pitboss act posted")
    _plain(text(found[0].get("body")))


def comment_edit(act: Act, target: Target, options: Options) -> str:
    """Replace the text of pitboss's own evidence comment (never a review or record).

    Args:
        act: the verb's world.
        target: the PR or issue.
        options: ``id`` and ``body``.

    Returns:
        What was done.
    """
    gate(act, "comment-edit", target.repo)
    identifier, body = option(options, "id"), option(options, "body")
    _own_comment(act, target, identifier)
    _plain(body)
    act.hub.write(
        Change(
            kind="comment-edit",
            repo=target.repo,
            number=target.number,
            fields={"id": identifier, "body": body},
        )
    )
    return f"comment-edit {identifier}"


def comment_delete(act: Act, target: Target, options: Options) -> str:
    """Delete pitboss's own evidence comment (never a review or record).

    Args:
        act: the verb's world.
        target: the PR or issue.
        options: ``id``.

    Returns:
        What was done.
    """
    gate(act, "comment-delete", target.repo)
    identifier = option(options, "id")
    _own_comment(act, target, identifier)
    act.hub.write(
        Change(
            kind="comment-delete",
            repo=target.repo,
            number=target.number,
            fields={"id": identifier},
        )
    )
    return f"comment-delete {identifier}"


def _body_rows(body: str, head: str, skip: Sequence[str]) -> None:
    if not FIXES.match(body):
        raise Refused("the body's first line is not `Fixes #N`")
    found = [
        each
        for each in totalbody.body_findings(body, head, {})
        if not any(word in each for word in skip)
    ]
    if found:
        raise Refused(found[0])


def pr_create(act: Act, target: Target, options: Options) -> str:
    """Open a PR whose body is in its form, for a ticket in its form.

    Args:
        act: the verb's world.
        target: the repository.
        options: ``head`` (the branch), ``title``, ``body`` and ``ticket`` (its body).

    Returns:
        The PR's number.
    """
    gate(act, "pr-create", target.repo)
    act.controls.items(option(options, "ticket"))
    body = option(options, "body")
    _body_rows(body, "", ("Head", "blocked by"))
    fields = {
        "head": option(options, "head"),
        "title": option(options, "title"),
        "body": body,
    }
    return act.hub.write(Change(kind="pr", repo=target.repo, fields=fields))


def pr_edit(act: Act, target: Target, options: Options) -> str:
    """Change a PR's title or body; an armed PR is disarmed first.

    Args:
        act: the verb's world.
        target: the PR.
        options: ``title`` and/or ``body``.

    Returns:
        What was done.
    """
    gate(act, "pr-edit", target.repo)
    fields = {key: options[key] for key in ("title", "body") if options.get(key)}
    if "body" in fields:
        _body_rows(
            fields["body"],
            head_of(act.hub.pull(target.repo, target.number)),
            ("blocked by",),
        )
    act.controls.disarm(act, target, "the body or the title changes")
    act.hub.write(
        Change(kind="pr-edit", repo=target.repo, number=target.number, fields=fields)
    )
    return f"pr-edit {target.repo}#{target.number}"


def scratch_clean(act: Act, target: Target, options: Options) -> str:
    """Delete a scratch branch and close its PR, in a scratch repository only.

    Args:
        act: the verb's world.
        target: the scratch repository and the PR (0 for none).
        options: ``branch``.

    Returns:
        What was done.

    Raises:
        Refused: not a scratch repository.
    """
    gate(act, "scratch-clean", target.repo)
    if target.repo not in SCRATCH:
        raise Refused(f"{target.repo} is not a scratch repository")
    if options.get("branch"):
        act.hub.write(
            Change(
                kind="branch-delete",
                repo=target.repo,
                fields={"branch": options["branch"]},
            )
        )
    if target.number:
        act.hub.write(Change(kind="pr-close", repo=target.repo, number=target.number))
    return f"scratch-clean {target.repo}"


def ack(act: Act, target: Target, options: Options) -> str:
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
        Refused: a kind in no row, or what it needs is missing.
    """
    message, kind = option(options, "message"), option(options, "kind")
    if kind not in ACKS:
        raise Refused(f"ack is {', '.join(ACKS)}")
    if kind == "hold":
        make_hold(act, target.repo, option(options, "scope"), message)
    elif kind == "cap":
        act.owner.cap = int(option(options, "cap"))
    elif kind == "ruling" and not text(options.get("reason")).startswith(("http", "#")):
        raise Refused("ack ruling names the ruling (a URL or #N)")
    elif kind == "none":
        _note(act, target, options)
    act.owner.dispositions[message] = kind
    return f"ack {message} {kind}"


def _note(act: Act, target: Target, options: Options) -> None:
    quote, reason = text(options.get("quote")), text(options.get("reason"))
    if not quote or len(reason) < 10:
        raise Refused("ack none quotes the message and gives a reason")
    repo = act.repos[0] if target.repo == "all" else target.repo
    fields = {
        "title": f"owner message {options['message']}: no action",
        "body": f"> {quote}\n\nreason: {reason}",
        "labels": ACK_LABEL,
    }
    act.hub.write(Change(kind="issue", repo=repo, fields=fields))
