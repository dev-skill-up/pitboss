"""The PR object, from GitHub's JSON to typed fields (plan section 6.1).

The one typed-field helper (``typed_or``) and the PR object's own fields; the
inputs read with it are ``pullstate`` (keyword: one-path).
"""

from typing import Mapping, Sequence, TypeVar

from . import schematypes
from .pullrecords import Closure, Merging, Mistyped, PullObject, Ticket, Unread, Where

Kind = TypeVar("Kind")
URL_FIELDS = ("comments_url", "commits_url", "html_url", "issue_url", "statuses_url")
Raw = Mapping[str, object]


def typed_or(value: object, kind: type[Kind], empty: Kind) -> Kind:
    """A value when it is of a kind (a bool is no int), else the kind's empty value.

    Args:
        value: what GitHub gave.
        kind: the type the field has.
        empty: what stands for it otherwise.

    Returns:
        The value or the empty one.
    """
    if isinstance(value, kind) and (kind is bool or not isinstance(value, bool)):
        return value
    return empty


def object_at(value: object, *path: str) -> Raw:
    """The JSON object at a path of objects.

    Args:
        value: what GitHub gave.
        *path: the names to follow.

    Returns:
        Its members by name; empty when a step is missing or it is no object.
    """
    for step in path:
        value = typed_or(value, dict, {}).get(step)
    return {str(name): each for name, each in typed_or(value, dict, {}).items()}


def count_at(value: object, name: str) -> int:
    """The whole number a member holds.

    Args:
        value: what GitHub gave.
        name: the member.

    Returns:
        The number; 0 when it is missing or no number.
    """
    return typed_or(object_at(value).get(name), int, 0)


def list_at(value: object, name: str) -> Sequence[object]:
    """The list a member holds.

    Args:
        value: what GitHub gave.
        name: the member.

    Returns:
        The list; empty when it is missing or no list.
    """
    return typed_or(object_at(value).get(name), list, [])


def text_at(value: object, *path: str) -> str:
    """The text at a path of objects.

    Args:
        value: what GitHub gave.
        *path: the names to follow.

    Returns:
        The text; empty when a step is missing or it is no text.
    """
    *above, last = path
    return typed_or(object_at(value, *above).get(last), str, "")


def _nullable(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _breaks(raw: Raw, schema: Mapping[str, str]) -> list[Mistyped]:
    found = []
    for name, declaration in schema.items():
        if name not in raw and schematypes.required(declaration):
            found.append(Mistyped(name=name, said="absent"))
        elif name in raw and not schematypes.typed(raw[name], declaration):
            found.append(Mistyped(name=name, said=str(raw[name])[:50]))
    return found


def _where(raw: Raw) -> Where:
    return Where(
        number=count_at(raw, "number"),
        url=str(raw.get("url")),
        links={name: _nullable(raw.get(name)) for name in URL_FIELDS},
        base_ref=text_at(raw, "base", "ref"),
        base_repo=text_at(raw, "base", "repo", "full_name"),
        head_sha=text_at(raw, "head", "sha"),
        head_ref=text_at(raw, "head", "ref"),
        head_repo=text_at(raw, "head", "repo", "full_name"),
        author=text_at(raw, "user", "login"),
        association=text_at(raw, "author_association"),
    )


def _closure(raw: Raw) -> Closure:
    merger = raw.get("merged_by")
    named = None if merger is None else text_at(merger, "login") or str(merger)
    return Closure(
        state=text_at(raw, "state"),
        closed_at=_nullable(raw.get("closed_at")),
        merged_at=_nullable(raw.get("merged_at")),
        merged_by=named,
        merged=bool(raw.get("merged")),
        locked=bool(raw.get("locked")),
        lock_reason=_nullable(raw.get("active_lock_reason")),
    )


def _merging(raw: Raw) -> Merging:
    return Merging(
        draft=bool(raw.get("draft")),
        mergeable=typed_or(raw.get("mergeable"), bool, None),
        mergeable_state=text_at(raw, "mergeable_state"),
        auto_merge=raw.get("auto_merge") is not None,
        labels=[text_at(each, "name") for each in list_at(raw, "labels")],
        reviewers=len(list_at(raw, "requested_reviewers")),
        teams=len(list_at(raw, "requested_teams")),
    )


def pull_object(raw: Raw, schema: Mapping[str, str]) -> PullObject:
    """The PR object, typed.

    Args:
        raw: the PR as GitHub answered.
        schema: each documented field's declaration.

    Returns:
        Its typed fields, each field as text, and its breaks.
    """
    return PullObject(
        where=_where(raw),
        closure=_closure(raw),
        merging=_merging(raw),
        title_is_text=isinstance(raw.get("title"), str),
        body_is_text=isinstance(raw.get("body"), (str, type(None))),
        body=text_at(raw, "body"),
        said={name: str(value)[:50] for name, value in raw.items()},
        breaks=_breaks(raw, schema),
    )


def said_at(each: Raw, name: str) -> str:
    """A member as the stop lines show it.

    Args:
        each: the object.
        name: the member.

    Returns:
        Its text; ``None`` when it is absent or null.
    """
    return str(each.get(name))


def _issue(value: object) -> Ticket | Unread:
    issue = object_at(value)
    if not isinstance(value, dict) or "_error" in issue:
        return Unread(why=text_at(issue, "_error"))
    return Ticket(
        state=said_at(issue, "state"),
        reason=said_at(issue, "state_reason"),
        locked=bool(issue.get("locked")),
        is_pull=bool(issue.get("pull_request")),
        body=text_at(issue, "body"),
    )


def tickets_of(read: object) -> Mapping[str, Ticket | Unread]:
    """Each ticket the body closes, typed.

    Args:
        read: the tickets as read, by reference.

    Returns:
        Each ticket, or why it was not read.
    """
    return {ref: _issue(issue) for ref, issue in object_at(read).items()}
