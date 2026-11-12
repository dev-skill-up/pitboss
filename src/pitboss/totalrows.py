"""A row for every field of the PR object (keyword: total-verdict).

Every documented field has a row: by default its documented type, and for the
fields a rule names, that rule. A field no rule names (``milestone``, ``stack``)
has a row that says so by being always satisfied, never a row that is missing.
"""

from typing import Callable, Mapping

from . import totalschema
from .totaljson import JsonMap, field, members, name_at, records, strings, text
from .totalanswer import GATED_ACTIONS, KNOWN_LABELS, MERGE_ACTIONS, PAUSED
from .totalreview import act_records

Row = Callable[[object, JsonMap, JsonMap], tuple[bool, str]]
MEMBERS = ("OWNER", "MEMBER", "COLLABORATOR")
URL_FIELDS = ("comments_url", "commits_url", "html_url", "issue_url", "statuses_url")
MERGES_ON = ("clean", "blocked", "has_hooks")


def action_of(ctx: JsonMap) -> str:
    """The action a verdict is asked for.

    Args:
        ctx: the inputs, with ``action``.

    Returns:
        The action.
    """
    return text(ctx.get("action"))


def _typed_row(declaration: str) -> Row:
    why = f"not of the documented type ({totalschema.head_of(declaration)})"
    return lambda value, pull, ctx: (totalschema.typed(value, declaration), why)


def _url(value: object, pull: JsonMap, ctx: JsonMap) -> tuple[bool, str]:
    return value is None or f"/{text(ctx.get('repo'))}/" in str(value), (
        "points at another repository"
    )


def _api_url(value: object, pull: JsonMap, ctx: JsonMap) -> tuple[bool, str]:
    want = f"repos/{text(ctx.get('repo'))}/pulls/{ctx.get('number')}"
    return str(value).endswith(want), "url names another repository or PR"


def _absent(why: str) -> Row:
    return lambda value, pull, ctx: (value is None, why)


def _draft(value: object, pull: JsonMap, ctx: JsonMap) -> tuple[bool, str]:
    return (not value) or action_of(ctx) in ("undraft", "disarm"), "the PR is a draft"


def _mergeable(value: object, pull: JsonMap, ctx: JsonMap) -> tuple[bool, str]:
    return value is True or action_of(ctx) not in MERGE_ACTIONS, (
        "GitHub does not say mergeable (false, or null while computing: the gate"
        " re-reads)"
    )


def _mergeable_state(value: object, pull: JsonMap, ctx: JsonMap) -> tuple[bool, str]:
    merges = value in MERGES_ON or (
        value == "behind" and ctx.get("merge_queue") is True
    )
    return action_of(ctx) not in MERGE_ACTIONS or merges, (
        "GitHub says the PR cannot merge now (it merges on clean; on blocked or"
        " has_hooks, whose causes are read here; on behind with a merge queue)"
    )


def _auto_merge(value: object, pull: JsonMap, ctx: JsonMap) -> tuple[bool, str]:
    timeline = records(ctx.get("timeline"))
    arms = act_records(timeline, text(ctx.get("act_identity")), "arm")
    head = name_at(pull, "head", "sha")
    armed = any(each == head for each, _ in arms)
    return value is None or action_of(ctx) == "disarm" or armed, (
        "auto-merge armed with no arm record for this head"
    )


def _base(value: object, pull: JsonMap, ctx: JsonMap) -> tuple[bool, str]:
    right = name_at(value, "ref") == ctx.get("default_branch")
    return right and name_at(value, "repo", "full_name") == ctx.get("repo"), (
        "the base is not the default branch of this repository"
    )


def _head(value: object, pull: JsonMap, ctx: JsonMap) -> tuple[bool, str]:
    return name_at(value, "repo", "full_name") == ctx.get("repo"), (
        "the head is not in this repository"
    )


def _labels(value: object, pull: JsonMap, ctx: JsonMap) -> tuple[bool, str]:
    names = [text(each.get("name")) for each in records(value)]
    known = all(each in KNOWN_LABELS for each in names)
    paused = action_of(ctx) in GATED_ACTIONS and PAUSED in names
    return known and not paused, (
        "a label pitboss does not apply, or paused-owner on merge, arm or undraft"
    )


def _no_rule(value: object, pull: JsonMap, ctx: JsonMap) -> tuple[bool, str]:
    return True, ""


def _user(value: object, pull: JsonMap, ctx: JsonMap) -> tuple[bool, str]:
    return name_at(value, "login") in strings(ctx.get("authors")), (
        "the author is not an agent identity or the owner"
    )


def _association(value: object, pull: JsonMap, ctx: JsonMap) -> tuple[bool, str]:
    login = name_at(pull, "user", "login")
    bot = login.endswith("[bot]") and login in strings(ctx.get("authors"))
    return value in MEMBERS or (value == "CONTRIBUTOR" and bot), (
        "the author is not a member"
    )


def _named_rows() -> Mapping[str, Row]:
    return {
        "number": lambda value, pull, ctx: (
            value == ctx.get("number"),
            "another PR number",
        ),
        "url": _api_url,
        "closed_at": _absent("the PR was closed"),
        "merged_at": _absent("the PR is merged"),
        "merged_by": _absent("the PR is merged"),
        "state": lambda value, pull, ctx: (value == "open", "the PR is not open"),
        "merged": lambda value, pull, ctx: (not value, "the PR is merged"),
        "draft": _draft,
        "locked": lambda value, pull, ctx: (not value, "the conversation is locked"),
        "active_lock_reason": _absent("the conversation is locked"),
        "mergeable": _mergeable,
        "mergeable_state": _mergeable_state,
        "auto_merge": _auto_merge,
        "base": _base,
        "head": _head,
        "title": lambda value, pull, ctx: (isinstance(value, str), "not text"),
        "labels": _labels,
        "milestone": _no_rule,  # no rule names a milestone
        "requested_reviewers": lambda value, pull, ctx: (
            not value,
            "a review was requested and not given",
        ),
        "requested_teams": lambda value, pull, ctx: (
            not value,
            "a team review was requested and not given",
        ),
        "user": _user,
        "author_association": _association,
        "stack": _no_rule,  # no rule names a stack
        "body": lambda value, pull, ctx: (
            value is None or isinstance(value, str),
            "not text",
        ),
    }


def rows(schema: Mapping[str, str]) -> Mapping[str, Row]:
    """The row of every field of the schema.

    Args:
        schema: each field's declaration.

    Returns:
        The rule of each field: its documented type, or the rule that names it.
    """
    found = {name: _typed_row(declaration) for name, declaration in schema.items()}
    found.update({name: _url for name in URL_FIELDS})
    found.update(_named_rows())
    return found


def ticket_state(ref: str, value: object) -> str:
    """The stop line of one ticket the body closes.

    Args:
        ref: the ticket.
        value: what was read of it.

    Returns:
        The line, ``""`` for an open issue that is not locked.
    """
    read = members(value)
    if not isinstance(value, dict) or "_error" in read:
        return f"ticket {ref}: not read ({text(field(value, '_error'))[:40]})"
    if read.get("pull_request"):
        return f"ticket {ref}: a pull request, not an issue"
    if read.get("state") != "open":
        return f"ticket {ref}: {read.get('state')} ({read.get('state_reason')})"
    return f"ticket {ref}: locked" if read.get("locked") else ""
