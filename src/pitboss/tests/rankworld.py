"""Worlds for the tests of the rank lines: BLOCKED, BLOCKS, PROMOTE (pitboss#388)."""

import re
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import config
from . import fakes, world

NEXT_LINE = re.compile(r"(?m)^NEXT \d+\. (\S+#\d+) \(")
PROJECT = world.PROJECT
PULL = f"{PROJECT}/pulls"
DEPENDENT = "Depends on owner/lib#3"
ISSUES = "/".join((world.PROJECT, "issues"))
LIST = fakes.page(ISSUES + "?state=open&labels=urgent")
COMMENTS = fakes.page(ISSUES + "/9/comments")
BLOCKER = "repos/owner/lib/issues/3"
LATER = {**world.TICKET, "number": 10, "created_at": "2026-09-02T00:00:00+00:00"}
REPOSITORY = config.make_repo("owner", "project")
LIB_THREE = {
    "state": "open",
    "labels": [],
    "title": "The dependency",
    "created_at": "2026-09-09T00:00:00Z",
    "body": "A ticket",
    "comments": 0,
}


def ticket(
    body: str = "", state: str = "open", number: int = 9, **changes: object
) -> Mapping[str, object]:
    """The JSON of a ticket as ``issues/<number>`` gives it.

    Args:
        body: its text.
        state: ``open`` or ``closed``.
        number: its number.
        **changes: fields to set in the JSON, such as ``labels`` or ``comments``.

    Returns:
        The JSON.
    """
    return {
        "number": number,
        "state": state,
        "labels": [{"name": "urgent"}],
        "title": "A ticket",
        "created_at": "2026-09-01T00:00:00+00:00",
        "body": body,
        "comments": 0,
        **changes,
    }


def serve(
    here: world.World, slug: str, number: int, found: Mapping[str, object]
) -> None:
    """Make the fake GitHub answer for a ticket.

    Args:
        here: the world.
        slug: its repository, ``owner/name``.
        number: its number.
        found: its JSON.
    """
    here.bodies[f"repos/{slug}/issues/{number}"] = dict(found)


def fixing(here: world.World, number: int, text: str) -> None:
    """Put a line at the top of the body of a PR of the project.

    Args:
        here: the world.
        number: the PR's number.
        text: the line, such as ``Fixes #9``.
    """
    found = here.bodies[f"{PULL}/{number}"]
    assert isinstance(found, dict)
    found["body"] = f"{text}\n\n{found['body']}"


def dependent_world(blocker: str = "open", pull: int = 3) -> world.World:
    """A PR fixes ticket 9, which depends on an open ticket of the library.

    Args:
        blocker: the state of ``owner/lib#3``.
        pull: the number of the PR of the project that fixes ticket 9.

    Returns:
        The world.
    """
    here = depends_world(DEPENDENT)
    here.bodies[BLOCKER] = {
        **LIB_THREE,
        "state": blocker,
    }
    serve(here, "owner/project", 9, ticket(DEPENDENT))
    fixing(here, pull, "Fixes #9")
    return here


def starts(here: world.World) -> Sequence[str]:
    """The references ``slots next`` lists, in the order of its NEXT lines.

    Args:
        here: the world.

    Returns:
        The references.
    """
    return NEXT_LINE.findall(next_output(here))


def mentioning(output: str, text: str) -> Sequence[str]:
    """The lines of an output that contain a text.

    Args:
        output: the output.
        text: what to look for.

    Returns:
        The lines.
    """
    return [each for each in output.splitlines() if text in each]


def lines_of(output: str, word: str) -> Sequence[str]:
    """The lines of an output that start with a word.

    Args:
        output: the output.
        word: the marker.

    Returns:
        The lines.
    """
    return [each for each in output.splitlines() if each.startswith(f"{word} ")]


def running(here: world.World) -> Sequence[str]:
    """The ``--running`` arguments that name the agents the ledger's rows hold.

    A test that is not about the derived slots passes these, so the live agents
    are the ones its ledger records (pitboss#94).

    Args:
        here: the world.

    Returns:
        ``--running`` and the name of each agent a row holds.
    """
    return ["--running", *re.findall(r'"agent": "([^"]+)"', here.ledger.read_text())]


def next_output(here: world.World) -> str:
    """What ``slots next`` prints, given the agents the ledger holds as live.

    Args:
        here: the world.

    Returns:
        Its output.
    """
    words = ["slots", "next", here.config, "--now", world.FUTURE, *running(here)]
    return world.invoke(here, *words).out


def sweep(here: world.World) -> world.Result:
    """Sweep a world at a time after everything in it.

    Args:
        here: the world.

    Returns:
        What the sweep did.
    """
    return world.again(here, "sweep", "--now", world.FUTURE, *running(here))


def comment(body: str, association: str = "MEMBER") -> Mapping[str, str]:
    """A comment on ticket 9.

    Args:
        body: its text.
        association: its author's association.

    Returns:
        The JSON of the comment.
    """
    return {
        "body": body,
        "author_association": association,
        "created_at": "2026-09-03T00:00:00Z",
    }


def blocked_world(
    body: str = "Cannot be worked on until owner/lib#3 has merged",
    state: str = "open",
    comments: Sequence[Mapping[str, str]] = (),
) -> world.World:
    """A world with ticket 9 that names a blocker, and a later ticket 10.

    Args:
        body: the body of ticket 9.
        state: the state of owner/lib#3.
        comments: the comments of ticket 9.

    Returns:
        The world.
    """
    here = world.make_world()
    ticket = {**world.TICKET, "body": body, "comments": len(comments)}
    here.bodies[LIST] = [ticket, LATER]
    here.bodies[COMMENTS] = list(comments)
    here.bodies[BLOCKER] = {
        "state": state,
        "labels": [],
        "title": "The blocker",
        "created_at": "2026-09-09T00:00:00Z",
    }
    return here


def depends_world(body: str) -> world.World:
    """Ticket 9 depends on an open ticket that has no priority label.

    Args:
        body: the body of ticket 9.

    Returns:
        The world.
    """
    here = blocked_world(body)
    here.bodies[BLOCKER] = dict(LIB_THREE)
    return here


def printed(here: world.World, word: str, expected: Sequence[str]) -> None:
    """Require the lines ``slots next`` prints under a marker.

    Args:
        here: the world.
        word: the marker.
        expected: the lines, in order.
    """
    assert_that(lines_of(next_output(here), word), equal_to(expected))


def lines_are(output: str, word: str, expected: Sequence[str]) -> None:
    """Require the lines of an output under a marker.

    Args:
        output: the output.
        word: the marker.
        expected: the lines, in order.
    """
    assert_that(lines_of(output, word), equal_to(expected))


def suggestions(here: world.World) -> str:
    """What ``next`` prints, given the agents the ledger holds as live.

    Args:
        here: the world.

    Returns:
        Its output.
    """
    args = ("next", "--now", world.FUTURE, *running(here))
    return world.again(here, *args).out


def ninth(here: world.World, body: str, state: str = "open", comments: int = 0) -> None:
    """Make the fake GitHub answer for ticket 9 of the project.

    Args:
        here: the world.
        body: its text.
        state: ``open`` or ``closed``.
        comments: how many comments it has.
    """
    serve(here, "owner/project", 9, ticket(body, state, comments=comments))


def publish(
    here: world.World, ranks: Sequence[str], tickets: Mapping[int, tuple[str, str]]
) -> None:
    """Make the fake GitHub list and answer for these tickets.

    Args:
        here: the world.
        ranks: the ``priority_labels``, each of which has a list.
        tickets: each ticket's number, label and state.
    """
    issues = {number: issue(number, *each) for number, each in tickets.items()}
    for wanted in ranks:
        listed = [issues[n] for n, each in tickets.items() if each == (wanted, "open")]
        for slug, found in ((PROJECT, listed), (world.LIBRARY, [])):
            here.bodies[fakes.page(f"{slug}/issues?state=open&labels={wanted}")] = found
    for number, each in issues.items():
        here.bodies[f"{PROJECT}/issues/{number}"] = each


def issue(number: int, label: str, state: str) -> Mapping[str, object]:
    """A ticket as the fake GitHub gives it.

    Args:
        number: its number; the day of September it was opened is that less 8.
        label: its label.
        state: ``open`` or ``closed``.

    Returns:
        The JSON of the ticket.
    """
    return {
        "number": number,
        "state": state,
        "title": "T",
        "created_at": f"2026-09-0{number - 8}T00:00:00Z",
        "labels": [{"name": label}],
    }


def absent(output: str, text: str) -> None:
    """Require that no line of an output mentions a text.

    Args:
        output: the output.
        text: what must not be there.
    """
    assert_that(mentioning(output, text), equal_to([]))
