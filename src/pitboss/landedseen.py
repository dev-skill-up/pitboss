"""What GitHub shows after each shape of write (keyword: landed, pitboss#531).

``watch_of`` gives, for the words of a write, a ``Watch``: what to read before the
write (a count, a newest number, a head) and the reading after it that shows the
write. Everything is read from GitHub with a GET; nothing here takes the write's
exit or its answer for the fact.
"""

import dataclasses
import functools
import json
import re
import subprocess
import urllib.parse
from typing import Callable, Mapping, Sequence

from .landedwords import Words, value_of
from .running import GitHub
from .totaljson import at, count, field, listing, records, text

Reading = Callable[[GitHub, Words], object]
Shown = Callable[[GitHub, Words, object], bool]
GET = ("gh", "api")
GONE = object()
PAGE = 100
CARET = {
    code: "^" + chr(code ^ 64) for code in (*range(9), 11, 12, *range(14, 32), 127)
}
QUERY = (
    "query($id: ID!) { node(id: $id) { ... on PullRequest"
    " { mergeQueueEntry { id } } } }"
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Watch:
    """How to see one write.

    Attributes:
        before: what is read before the write.
        seen: whether the reading after it shows the write (the reading before
            is the second argument).
    """

    before: Reading
    seen: Shown


def _missing(error: subprocess.CalledProcessError) -> object:
    # a 404 is GitHub's answer that the path is not there; any other failure is not
    if "HTTP 404" in f"{error.stderr or ''}{error.stdout or ''}":
        return GONE
    raise error


def get(github: GitHub, path: str) -> object:
    """One GET, as the JSON it holds; ``GONE`` for a 404.

    Args:
        github: the API.
        path: the path.

    Returns:
        The value.

    Any other failure is raised: GitHub not answering is not an answer.
    """
    try:
        answer = json.loads(github.run([*GET, path]).stdout or "null")
    except subprocess.CalledProcessError as error:
        answer = _missing(error)
    return answer


def _every(github: GitHub, path: str) -> Sequence[Mapping[str, object]]:
    joined = "&" if "?" in path else "?"
    found: list[Mapping[str, object]] = []
    page = 0
    while True:
        page += 1
        got = records(get(github, f"{path}{joined}per_page={PAGE}&page={page}"))
        found += got
        if len(got) < PAGE:
            return found


def same(left: object, right: str) -> bool:
    """Whether a text GitHub holds is the one that was sent.

    Args:
        left: what GitHub holds.
        right: what was sent.

    Returns:
        True when it holds the text sent, a line end and the ends' blanks apart,
        with anything after it (a footer the host adds to what it keeps).
    """

    def plain(each: str) -> str:
        # the host may write a control character as ``^[`` (caret notation)
        return each.translate(CARET).replace("\r\n", "\n").strip()

    return plain(text(left)).startswith(plain(right))


def _nothing(github: GitHub, write: Words) -> object:
    return None


def _bodies(github: GitHub, write: Words) -> int:
    # the comments already holding the body (a comment may be posted twice)
    path = write.path
    wanted = value_of(write, "body")
    return len(
        [each for each in _every(github, path) if same(each.get("body"), wanted)]
    )


def _more_bodies(github: GitHub, write: Words, before: object) -> bool:
    return isinstance(before, int) and _bodies(github, write) > before


def _held(github: GitHub, write: Words, name: str) -> object:
    return field(get(github, write.path), name)


def _edited(github: GitHub, write: Words, before: object) -> bool:
    return same(_held(github, write, "body"), value_of(write, "body"))


def _gone(github: GitHub, write: Words, before: object) -> bool:
    return get(github, write.path) is GONE


def _repo(write: Words) -> str:
    return "/".join(write.path.split("/")[:3])


def _newest(github: GitHub, write: Words, kind: str) -> int:
    path = f"{_repo(write)}/{kind}?state=open&sort=created&direction=desc&per_page=1"
    return max(
        (count(each, "number") for each in records(get(github, path))), default=0
    )


def _newer(before: object, each: Mapping[str, object]) -> bool:
    return count(each, "number") > (before if isinstance(before, int) else 0)


def _made_issue(github: GitHub, write: Words, before: object) -> bool:
    path = f"{_repo(write)}/issues?state=open&sort=created&direction=desc&per_page=30"
    return any(
        _newer(before, each)
        and "pull_request" not in each
        and same(each.get("title"), value_of(write, "title"))
        for each in records(get(github, path))
    )


def _made_pull(github: GitHub, write: Words, before: object) -> bool:
    owner = _repo(write).split("/")[1]
    head = value_of(write, "head")
    named = urllib.parse.quote(head if ":" in head else f"{owner}:{head}")
    path = f"{_repo(write)}/pulls?state=open&head={named}&per_page=30"
    return any(map(functools.partial(_newer, before), records(get(github, path))))


def _patched(github: GitHub, write: Words, before: object) -> bool:
    # a PR or an issue holds each field the PATCH sent
    held = get(github, write.path)
    return all(
        same(field(held, name), value_of(write, name))
        for name in ("title", "body", "state")
        if name in write.fields
    )


def _flag(name: str, value: bool, strip: str = "") -> Shown:
    # the PR's field ``name`` is ``value``, read at the path without ``strip``
    def shown(github: GitHub, write: Words, before: object) -> bool:
        return field(get(github, write.path.removesuffix(strip)), name) is value

    return shown


_merged = _flag("merged", True, "/merge")
_undrafted = _flag("draft", False)


def _armed(github: GitHub, write: Words, before: object) -> bool:
    held = _held(github, write, "auto_merge")
    return not held if "--disable-auto" in write.flags else bool(held)


def _pr_merge_seen(github: GitHub, write: Words, before: object) -> bool:
    if "--auto" in write.flags or "--disable-auto" in write.flags:
        return _armed(github, write, before)
    return _merged(github, write, before)


def _label_names(github: GitHub, path: str) -> Sequence[str]:
    held = records(field(get(github, path), "labels"))
    return [text(each.get("name")) for each in held]


def _labelled(github: GitHub, write: Words, before: object) -> bool:
    path = write.path.rsplit("/labels", 1)[0]
    return value_of(write, "labels[]") in _label_names(github, path)


def _unlabelled(github: GitHub, write: Words, before: object) -> bool:
    path, _, name = write.path.rpartition("/labels/")
    return urllib.parse.unquote(name) not in _label_names(github, path)


def _ref_gone(github: GitHub, write: Words, before: object) -> bool:
    return get(github, write.path.replace("/git/refs/", "/git/ref/")) is GONE


def _pull_head(github: GitHub, write: Words) -> object:
    path = write.path.removesuffix("/update-branch")
    return text(at(get(github, path), "head", "sha"))


def _moved(github: GitHub, write: Words, before: object) -> bool:
    return _pull_head(github, write) != before


def _run_path(write: Words) -> str:
    return write.path.rsplit("/", 1)[0]


def _rerun(github: GitHub, write: Words, before: object) -> bool:
    return field(get(github, _run_path(write)), "status") != "completed"


def _cancelled(github: GitHub, write: Words, before: object) -> bool:
    held = get(github, _run_path(write))
    return (
        field(held, "status") == "completed" or field(held, "conclusion") == "cancelled"
    )


def _latest_dispatch(github: GitHub, write: Words) -> object:
    path = (
        write.path.removesuffix("/dispatches")
        + "/runs?event=workflow_dispatch&per_page=1"
    )
    return [
        count(each, "id")
        for each in listing(field(get(github, path), "workflow_runs"))
        if isinstance(each, dict)
    ]


def _dispatched(github: GitHub, write: Words, before: object) -> bool:
    return _latest_dispatch(github, write) != before


def _queue_entry(github: GitHub, write: Words) -> object:
    words = [
        "gh",
        "api",
        "graphql",
        "-f",
        f"query={QUERY}",
        "-f",
        f"id={value_of(write, 'id')}",
    ]
    return json.loads(github.run(words).stdout or "null")


def _dequeued(github: GitHub, write: Words, before: object) -> bool:
    entry = _queue_entry(github, write)
    return at(entry, "data", "node", "mergeQueueEntry") is None


RULES: Sequence[tuple[str, str, Watch]] = (
    (
        "POST",
        r"repos/[^/]+/[^/]+/issues/\d+/comments",
        Watch(before=_bodies, seen=_more_bodies),
    ),
    (
        "PATCH",
        r"repos/[^/]+/[^/]+/issues/comments/\d+",
        Watch(before=_nothing, seen=_edited),
    ),
    (
        "DELETE",
        r"repos/[^/]+/[^/]+/issues/comments/\d+",
        Watch(before=_nothing, seen=_gone),
    ),
    (
        "POST",
        r"repos/[^/]+/[^/]+/issues",
        Watch(before=functools.partial(_newest, kind="issues"), seen=_made_issue),
    ),
    (
        "POST",
        r"repos/[^/]+/[^/]+/pulls",
        Watch(before=functools.partial(_newest, kind="pulls"), seen=_made_pull),
    ),
    (
        "PATCH",
        r"repos/[^/]+/[^/]+/(?:issues|pulls)/\d+",
        Watch(before=_nothing, seen=_patched),
    ),
    ("PUT", r"repos/[^/]+/[^/]+/pulls/\d+/merge", Watch(before=_nothing, seen=_merged)),
    (
        "PUT",
        r"repos/[^/]+/[^/]+/pulls/\d+/update-branch",
        Watch(before=_pull_head, seen=_moved),
    ),
    ("PR-MERGE", r".*", Watch(before=_nothing, seen=_pr_merge_seen)),
    ("PR-READY", r".*", Watch(before=_nothing, seen=_undrafted)),
    (
        "POST",
        r"repos/[^/]+/[^/]+/issues/\d+/labels",
        Watch(before=_nothing, seen=_labelled),
    ),
    (
        "DELETE",
        r"repos/[^/]+/[^/]+/issues/\d+/labels/.+",
        Watch(before=_nothing, seen=_unlabelled),
    ),
    (
        "DELETE",
        r"repos/[^/]+/[^/]+/git/refs/heads/.+",
        Watch(before=_nothing, seen=_ref_gone),
    ),
    (
        "POST",
        r"repos/[^/]+/[^/]+/actions/runs/\d+/rerun-failed-jobs",
        Watch(before=_nothing, seen=_rerun),
    ),
    (
        "POST",
        r"repos/[^/]+/[^/]+/actions/runs/\d+/cancel",
        Watch(before=_nothing, seen=_cancelled),
    ),
    (
        "POST",
        r"repos/[^/]+/[^/]+/actions/workflows/[^/]+/dispatches",
        Watch(before=_latest_dispatch, seen=_dispatched),
    ),
    ("POST", r"graphql", Watch(before=_nothing, seen=_dequeued)),
)


def watch_of(write: Words) -> Watch | None:
    """What shows a write.

    Args:
        write: the write.

    Returns:
        The first rule of ``RULES`` whose verb and path are the write's, None when
        none is.
    """
    return next(
        (
            each
            for verb, path, each in RULES
            if verb == write.verb and re.fullmatch(path, write.path)
        ),
        None,
    )
