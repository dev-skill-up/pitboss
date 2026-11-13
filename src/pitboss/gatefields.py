"""A row for every documented field of the PR object, on typed state (keyword: gate).

Every documented field has a row: by default its documented type, and for the
fields a rule names, that rule (plan 6.1: the rows read the typed state
``pullstate`` made, never the JSON). A field no rule names (``milestone``,
``stack``) has a row that says so by being always satisfied.
"""

from typing import Callable, Mapping, Sequence

from . import schematypes, totalreview
from .gaterows import listed
from .gatestop import Route, Stop
from .pullrecords import GateState, Merging
from .totalanswer import GATED_ACTIONS, KNOWN_LABELS, MERGE_ACTIONS, PAUSED

Check = Callable[[GateState, str], bool]
MEMBERS = ("OWNER", "MEMBER", "COLLABORATOR")
URL_FIELDS = ("comments_url", "commits_url", "html_url", "issue_url", "statuses_url")
MERGES_ON = ("clean", "blocked", "has_hooks")
# the actions a draft does not stop
DRAFT_ACTIONS = frozenset({"undraft", "disarm"})
CLOSED_FIELDS = frozenset({"state", "merged", "merged_at", "merged_by", "closed_at"})
FOREIGN_FIELDS = frozenset(
    {"number", "url", "base", "head", "user", "author_association", *URL_FIELDS}
)
FIELD_ROUTES: Mapping[str, Route] = {
    "draft": Route.UNDRAFT,
    "auto_merge": Route.DISARM,
    "mergeable": Route.UNDECIDED,
    "locked": Route.LOCK,
    "active_lock_reason": Route.LOCK,
    "requested_reviewers": Route.REVIEWERS,
    "requested_teams": Route.REVIEWERS,
    **{name: Route.CLOSED for name in CLOSED_FIELDS},
    **{name: Route.FOREIGN for name in FOREIGN_FIELDS},
}
MERGEABLE_ROUTES: Mapping[str, Route] = {
    "dirty": Route.CONFLICT,
    "behind": Route.BEHIND,
    "unstable": Route.UNSTABLE,
    "draft": Route.UNDRAFT,
}


def _url(name: str) -> Check:
    def check(state: GateState, action: str) -> bool:
        link = state.pull.where.links.get(name)
        return link is None or f"/{state.repository.repo}/" in link

    return check


def _api_url(state: GateState, action: str) -> bool:
    want = f"repos/{state.repository.repo}/pulls/{state.repository.number}"
    return state.pull.where.url.endswith(want)


def _draft(state: GateState, action: str) -> bool:
    return not state.pull.merging.draft or action in DRAFT_ACTIONS


def _mergeable(state: GateState, action: str) -> bool:
    return state.pull.merging.mergeable is True or action not in MERGE_ACTIONS


def _mergeable_state(state: GateState, action: str) -> bool:
    said = state.pull.merging.mergeable_state
    merges = said in MERGES_ON or (said == "behind" and state.repository.merge_queue)
    return action not in MERGE_ACTIONS or merges


def _auto_merge(state: GateState, action: str) -> bool:
    identity = state.repository.identity
    arms = totalreview.act_records(listed(state.reads.timeline), identity, "arm")
    armed = any(each == state.pull.where.head_sha for each, _ in arms)
    return not state.pull.merging.auto_merge or action == "disarm" or armed


def _base(state: GateState, action: str) -> bool:
    where, repository = state.pull.where, state.repository
    right = where.base_ref == repository.default_branch
    return right and where.base_repo == repository.repo


def _head(state: GateState, action: str) -> bool:
    return state.pull.where.head_repo == state.repository.repo


def _labels(state: GateState, action: str) -> bool:
    names = state.pull.merging.labels
    known = all(each in KNOWN_LABELS for each in names)
    return known and not (action in GATED_ACTIONS and PAUSED in names)


def _user(state: GateState, action: str) -> bool:
    return state.pull.where.author in state.repository.authors


def _association(state: GateState, action: str) -> bool:
    login, said = state.pull.where.author, state.pull.where.association
    bot = login.endswith("[bot]") and login in state.repository.authors
    return said in MEMBERS or (said == "CONTRIBUTOR" and bot)


def _closure(read: Callable[[GateState], object]) -> Check:
    # a field of the PR's closure that holds nothing while it is open
    return lambda state, action: not read(state)


ROWS: Mapping[str, tuple[Check, str]] = {
    "number": (
        lambda state, action: state.pull.where.number == state.repository.number,
        "another PR number",
    ),
    "url": (_api_url, "url names another repository or PR"),
    **{name: (_url(name), "points at another repository") for name in URL_FIELDS},
    "closed_at": (
        _closure(lambda state: state.pull.closure.closed_at),
        "the PR was closed",
    ),
    "merged_at": (
        _closure(lambda state: state.pull.closure.merged_at),
        "the PR is merged",
    ),
    "merged_by": (
        _closure(lambda state: state.pull.closure.merged_by),
        "the PR is merged",
    ),
    "state": (
        lambda state, action: state.pull.closure.state == "open",
        "the PR is not open",
    ),
    "merged": (_closure(lambda state: state.pull.closure.merged), "the PR is merged"),
    "draft": (_draft, "the PR is a draft"),
    "locked": (
        _closure(lambda state: state.pull.closure.locked),
        "the conversation is locked",
    ),
    "active_lock_reason": (
        _closure(lambda state: state.pull.closure.lock_reason),
        "the conversation is locked",
    ),
    "mergeable": (
        _mergeable,
        "GitHub does not say mergeable (false, or null while computing: the gate"
        " re-reads)",
    ),
    "mergeable_state": (
        _mergeable_state,
        "GitHub says the PR cannot merge now (it merges on clean; on blocked or"
        " has_hooks, whose causes are read here; on behind with a merge queue)",
    ),
    "auto_merge": (_auto_merge, "auto-merge armed with no arm record for this head"),
    "base": (_base, "the base is not the default branch of this repository"),
    "head": (_head, "the head is not in this repository"),
    "title": (lambda state, action: state.pull.title_is_text, "not text"),
    "labels": (
        _labels,
        "a label pitboss does not apply, or paused-owner on merge, arm or undraft",
    ),
    "milestone": (lambda state, action: True, ""),  # no rule names a milestone
    "requested_reviewers": (
        _closure(lambda state: state.pull.merging.reviewers),
        "a review was requested and not given",
    ),
    "requested_teams": (
        _closure(lambda state: state.pull.merging.teams),
        "a team review was requested and not given",
    ),
    "user": (_user, "the author is not an agent identity or the owner"),
    "author_association": (_association, "the author is not a member"),
    "stack": (lambda state, action: True, ""),  # no rule names a stack
    "body": (lambda state, action: state.pull.body_is_text, "not text"),
}


def _labels_route(merging: Merging) -> Route:
    return Route.PAUSED if PAUSED in merging.labels else Route.LABEL


def _merge_route(merging: Merging) -> Route:
    return MERGEABLE_ROUTES.get(merging.mergeable_state, Route.UNDECIDED)


# the fields whose route depends on what GitHub says of the PR
ROUTED_BY: Mapping[str, Callable[[Merging], Route]] = {
    "labels": _labels_route,
    "mergeable_state": _merge_route,
}


def _route(name: str, state: GateState) -> Route:
    found = ROUTED_BY.get(name)
    if found is not None:
        return found(state.pull.merging)
    return FIELD_ROUTES.get(name, Route.UNREAD)


def _why(name: str, declaration: str, state: GateState, action: str) -> str:
    # why the field's row fails, "" when it holds
    said, mistyped = state.pull.said, {each.name for each in state.pull.breaks}
    present = name in said
    row = ROWS.get(name)
    if row is not None:
        check, why = row
        if not check(state, action):
            return why
        return "not of the documented type" if present and name in mistyped else ""
    typed = name not in mistyped if present else schematypes.typed(None, declaration)
    head = schematypes.head_of(declaration)
    return "" if typed else f"not of the documented type ({head})"


def field_stops(
    state: GateState, action: str, schema: Mapping[str, str]
) -> Sequence[Stop]:
    """The stops of the PR's own fields, one row for each documented field.

    Args:
        state: the typed state.
        action: the action.
        schema: each field's declaration.

    Returns:
        A stop for each field whose row fails, and each required field absent.
    """
    said = state.pull.said
    found = [
        Stop(route=_route(name, state), line=f"{name}={said.get(name, 'None')}: {why}")
        for name, declaration in schema.items()
        if (why := _why(name, declaration, state, action))
    ]
    found += [
        Stop(route=Route.UNREAD, line=f"{name}: a required field is absent")
        for name, declaration in schema.items()
        if schematypes.required(declaration) and name not in said
    ]
    return found
