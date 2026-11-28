"""What a write does to a fake GitHub's bodies, so the read after it shows it (landed).

The worlds can their reads as bodies by path; a write that goes through
``landed.checked`` is read back, so the fake changes the bodies as GitHub does.
"""

import re
from typing import Callable, MutableMapping, Sequence

from ..landedwords import Words, parse, value_of

Bodies = MutableMapping[str, object]
Rule = Callable[[Bodies, Words, re.Match[str]], None]
SHAPE = r"(repos/[^/]+/[^/]+)"


def page(path: str, number: int = 1) -> str:
    """The path ``ghapi.pages`` asks for.

    Args:
        path: the list's path.
        number: the page.

    Returns:
        The paged path.
    """
    separator = "&" if "?" in path else "?"
    return f"{path}{separator}per_page=100&page={number}"


def _held(bodies: Bodies, path: str) -> dict[str, object]:
    # the dictionary a path holds; made when the world has none
    found = bodies.get(path)
    if not isinstance(found, dict):
        found = bodies[path] = {}
    return found


def _comment_posted(bodies: Bodies, write: Words, found: re.Match[str]) -> None:
    key = page(write.path)
    listed = bodies.get(key)
    if not isinstance(listed, list):
        listed = bodies[key] = []
    listed.append({"id": 1000 + len(listed), "body": value_of(write, "body")})


def _comment_edited(bodies: Bodies, write: Words, found: re.Match[str]) -> None:
    _held(bodies, write.path)["body"] = value_of(write, "body")


def _labelled(bodies: Bodies, write: Words, found: re.Match[str]) -> None:
    for kind in ("issues", "pulls"):
        path = f"{found.group(1)}/{kind}/{found.group(2)}"
        if path in bodies:
            labels = _held(bodies, path).setdefault("labels", [])
            assert isinstance(labels, list)
            labels.append({"name": value_of(write, "labels[]")})


def _unlabelled(bodies: Bodies, write: Words, found: re.Match[str]) -> None:
    name = found.group(3).replace("%20", " ")
    for kind in ("issues", "pulls"):
        path = f"{found.group(1)}/{kind}/{found.group(2)}"
        if path in bodies:
            kept = [
                each
                for each in _list(_held(bodies, path).get("labels"))
                if each.get("name") != name
            ]
            _held(bodies, path)["labels"] = kept


def _list(value: object) -> list[dict[str, object]]:
    return (
        [each for each in value if isinstance(each, dict)]
        if isinstance(value, list)
        else []
    )


def _pulled(bodies: Bodies, write: Words, found: re.Match[str]) -> None:
    pull = _held(bodies, f"{found.group(1)}/pulls/{found.group(2)}")
    if "--disable-auto" in write.flags:
        pull["auto_merge"] = None
    elif "--auto" in write.flags:
        pull["auto_merge"] = {"enabled_by": {"login": "fake"}}
    elif write.verb == "PR-READY":
        pull["draft"] = False
    else:
        pull["merged"] = True


def _patched(bodies: Bodies, write: Words, found: re.Match[str]) -> None:
    held = _held(bodies, write.path)
    held.update({name: values[0] for name, values in write.fields.items() if values})


def _dropped(moved: Callable[[str], str]) -> Rule:
    # the path (as ``moved`` names it) is no longer held
    def rule(bodies: Bodies, write: Words, found: re.Match[str]) -> None:
        bodies.pop(moved(write.path), None)

    return rule


def _sets(path: Callable[[str], str], name: str, value: object) -> Rule:
    # the path (as ``path`` names it) holds ``value`` at ``name``
    def rule(bodies: Bodies, write: Words, found: re.Match[str]) -> None:
        _held(bodies, path(write.path))[name] = value

    return rule


def _branch_updated(bodies: Bodies, write: Words, found: re.Match[str]) -> None:
    pull = _held(bodies, write.path.removesuffix("/update-branch"))
    head = pull.get("head")
    if isinstance(head, dict):
        head["sha"] = "f" * 40


_PULL = lambda path: path.removesuffix("/merge")  # noqa: E731
_REF = lambda path: path.replace("/git/refs/", "/git/ref/")  # noqa: E731
_RUN = lambda path: path.rsplit("/", 1)[0]  # noqa: E731
RULES: Sequence[tuple[str, str, Rule]] = (
    ("POST", SHAPE + r"/issues/(\d+)/comments", _comment_posted),
    ("PATCH", SHAPE + r"/issues/comments/\d+", _comment_edited),
    ("DELETE", SHAPE + r"/issues/comments/\d+", _dropped(str)),
    ("POST", SHAPE + r"/issues/(\d+)/labels", _labelled),
    ("DELETE", SHAPE + r"/issues/(\d+)/labels/(.+)", _unlabelled),
    ("PR-MERGE", SHAPE + r"/pulls/(\d+)", _pulled),
    ("PR-READY", SHAPE + r"/pulls/(\d+)", _pulled),
    ("PUT", SHAPE + r"/pulls/\d+/merge", _sets(_PULL, "merged", True)),
    ("PATCH", SHAPE + r"/(?:pulls|issues)/\d+", _patched),
    ("DELETE", SHAPE + r"/git/refs/.+", _dropped(_REF)),
    ("PUT", SHAPE + r"/pulls/\d+/update-branch", _branch_updated),
    (
        "POST",
        SHAPE + r"/actions/runs/\d+/rerun-failed-jobs",
        _sets(_RUN, "status", "queued"),
    ),
    ("POST", SHAPE + r"/actions/runs/\d+/cancel", _sets(_RUN, "status", "completed")),
)


def apply(bodies: Bodies, command: Sequence[str]) -> None:
    """Change a fake GitHub's bodies as a write would.

    Args:
        bodies: the world's bodies.
        command: the ``gh`` line of the write (any other line changes nothing).
    """
    write = parse(command)
    for verb, shape, rule in RULES if write else ():
        found = re.fullmatch(shape, write.path) if write else None
        if write and found and write.verb == verb:
            rule(bodies, write, found)
            return
