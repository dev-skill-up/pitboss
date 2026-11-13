"""The PR object, from GitHub's JSON to typed fields (plan section 6.1).

The one typed-field helper (``typed_or``) and the PR object's own fields; the
inputs read with it are ``pullstate`` (keyword: one-path).
"""

from typing import Mapping, Sequence, TypeVar

from . import schematypes
from .pullrecords import Closure, Merging, Mistyped, PullObject, Where

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
        head_repo=text_at(raw, "head", "repo", "full_name"),
        author=text_at(raw, "user", "login"),
        association=text_at(raw, "author_association"),
    )


def _closure(raw: Raw) -> Closure:
    merger = raw.get("merged_by")
    return Closure(
        state=text_at(raw, "state"),
        closed_at=_nullable(raw.get("closed_at")),
        merged_at=_nullable(raw.get("merged_at")),
        merged_by=text_at(merger, "login") or _nullable(merger),
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
        body=text_at(raw, "body"),
        said={name: str(value)[:50] for name, value in raw.items()},
        breaks=_breaks(raw, schema),
    )
