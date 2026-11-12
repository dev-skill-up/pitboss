"""Replaying a captured timeline at a moment of it (keyword: scenario, pitboss#444).

``pitboss capture-timeline`` writes what GitHub recorded of a real PR. ``state_at``
gives the ``PullState`` the flow would have read at a time: the comments, reviews,
label and draft events and check runs up to it, and the head the newest commit
made. The PR's body is its final text, since GitHub keeps no history of a body,
and the merge state is clean: a mark is placed where those two hold.
"""

import enum
import json
import pathlib
from typing import AbstractSet, Mapping, NamedTuple, Sequence, TypedDict

from .. import capture, config, flow, parsing, reviews, shapes, steps

DIRECTORY = pathlib.Path(__file__).with_name("scenarios")
HEADER = "Independent review (a separate reviewer agent, not the author) of head"
FORM = config.ReviewForm(
    lines=(f"{HEADER} {{sha}}: {{verdict}}",),
    approved="approved",
    changes_needed="changes needed",
)
REVIEW = config.Review(
    trusted=frozenset({"OWNER", "MEMBER", "COLLABORATOR"}),
    gated=frozenset(),
    form=FORM,
    gated_form=FORM,
)
Item = Mapping[str, object]


class Timeline(TypedDict):
    """What ``pitboss capture-timeline`` wrote.

    Attributes:
        slug: the repository.
        number: the PR's number.
        pull: the PR as the API gave it, flattened.
        comments: its comments.
        reviews: its formal reviews.
        events: its label and draft events.
        commits: the commits that made its heads.
        checks: the check runs of each head.
    """

    slug: str
    number: int
    pull: Item
    comments: Sequence[Item]
    reviews: Sequence[Item]
    events: Sequence[Item]
    commits: Sequence[Item]
    checks: Mapping[str, Sequence[Item]]


class Event(enum.Enum):
    """The events of a PR's timeline that the replay reads.

    Attributes:
        LABELED: a label was added.
        UNLABELED: a label was removed.
        READY: the PR was marked ready for review.
        DRAFTED: the PR was converted to a draft.
    """

    LABELED = enum.auto()
    UNLABELED = enum.auto()
    READY = enum.auto()
    DRAFTED = enum.auto()


NAMED = {
    "labeled": Event.LABELED,
    "unlabeled": Event.UNLABELED,
    "ready_for_review": Event.READY,
    "convert_to_draft": Event.DRAFTED,
}

DRAFTING = (Event.READY, Event.DRAFTED)


class Mark(NamedTuple):
    """A moment of a timeline and the step the rules require there.

    Attributes:
        when: the time (ISO 8601) the PR is read at.
        rule: the rule id the mark shows.
        want: the step the rules require, as ``kind`` names it.
        settled: whether CI is read as finished (``state_at``).
    """

    when: str
    rule: str
    want: str
    settled: bool = True


def load(name: str) -> Timeline:
    """Read a captured timeline.

    Args:
        name: the file's name in ``scenarios`` without ``.json``
            (``dev-skill-up-pitboss-465``).

    Returns:
        The timeline.
    """
    text = (DIRECTORY / f"{name}.json").read_text(encoding="utf-8")
    data: Timeline = json.loads(text)
    return data


def _before(items: Sequence[Item], field: str, when: str) -> Sequence[Item]:
    return [each for each in items if str(each[field] or "") <= when]


def labels_at(data: Timeline, when: str) -> AbstractSet[str]:
    """The labels the PR carried at a time.

    Args:
        data: the timeline.
        when: the time.

    Returns:
        The label names after the events up to ``when``.
    """
    named: set[str] = set()
    for each in _before(data["events"], "created_at", when):
        happened = NAMED[str(each["event"])]
        if happened is Event.LABELED:
            named.add(str(each["label"]))
        elif happened is Event.UNLABELED:
            named.discard(str(each["label"]))
    return named


def draft_at(data: Timeline, when: str) -> bool:
    """Whether the PR was a draft at a time.

    Args:
        data: the timeline.
        when: the time.

    Returns:
        The state after the draft events up to ``when``; before any, the state
        the first event leaves (a PR made ready began as a draft); with none,
        the state the PR has.
    """
    marks = [each for each in data["events"] if NAMED[str(each["event"])] in DRAFTING]
    drafted = bool(data["pull"]["draft"])
    state = NAMED[str(marks[0]["event"])] is Event.READY if marks else drafted
    for each in _before(marks, "created_at", when):
        state = NAMED[str(each["event"])] is Event.DRAFTED
    return bool(state)


def head_at(data: Timeline, when: str) -> str:
    """The sha of the head at a time.

    Args:
        data: the timeline.
        when: the time.

    Returns:
        The newest commit made by then (the first when none was).
    """
    made = _before(data["commits"], "date", when)
    return str((made or data["commits"])[-1 if made else 0]["sha"])


def _run(each: Item, when: str, settled: bool) -> Item:
    done = settled or str(each["completed_at"] or "~") <= when
    return {
        **each,
        "status": each["status"] if done else "in_progress",
        "conclusion": each["conclusion"] if done else None,
    }


def _checks(
    data: Timeline, head: str, when: str, settled: bool
) -> Sequence[shapes.CheckRun]:
    every = data["checks"].get(head, ())
    started = _before(every, "started_at", when)
    runs = [_run(each, when, settled) for each in started]
    return parsing.check_runs(json.dumps({"check_runs": runs}))


def _pull(data: Timeline, when: str) -> str:
    changes = {
        "head": {
            "sha": head_at(data, when),
            "ref": capture.as_object(data["pull"]["head"])["ref"],
        },
        "draft": draft_at(data, when),
        "mergeable_state": "clean",
    }
    return json.dumps({**data["pull"], **changes})


def _posted(data: Timeline, when: str) -> reviews.Sources:
    comments = _before(data["comments"], "created_at", when)
    given = _before(data["reviews"], "submitted_at", when)
    return reviews.Sources(
        comments=parsing.comments(json.dumps(comments)),
        reviews=parsing.reviews(json.dumps(given)),
    )


def state_at(data: Timeline, when: str, settled: bool = False) -> flow.PullState:
    """What the flow reads of the PR at a time.

    Args:
        data: the timeline.
        when: the time (ISO 8601, as GitHub writes it).
        settled: whether the checks started by then are read as finished (as
            they ended), for a mark whose step does not depend on CI's timing.

    Returns:
        The state, with the labels, draft state, head, checks, comments and
        reviews of that time.
    """
    posted = _posted(data, when)
    pull = parsing.pull(_pull(data, when))
    return flow.PullState(
        pull=pull,
        labels=labels_at(data, when),
        checks=_checks(data, pull.head.sha, when, settled),
        graded=reviews.recorded(REVIEW, data["slug"], posted),
        comments=posted.comments,
        trusted=REVIEW.trusted,
    )


def kind(step: steps.Next) -> str:
    """The name of a step: its step, then its task or stage.

    Args:
        step: the step.

    Returns:
        ``WORKER:RULING_STEPS``, ``REGULAR_REVIEW:RULING_STEPS``, ``MERGE``.
    """
    named = [step.step.name]
    named += [step.task.name] if step.task else []
    named += [step.stage.name] if step.stage else []
    return ":".join(named)


def step_at(data: Timeline, when: str, settled: bool = False) -> steps.Next:
    """The step the flow gives the PR at a time.

    Args:
        data: the timeline.
        when: the time.
        settled: as for ``state_at``.

    Returns:
        The step.
    """
    return flow.next_step(state_at(data, when, settled))


def printed(name: str, mark: Mark) -> str:
    """The line a scenario prints at a mark: what the flow gives there.

    Args:
        name: the timeline's name.
        mark: the mark.

    Returns:
        The line, with the step ``steps.describe`` says.
    """
    step = step_at(load(name), mark.when, mark.settled)
    return f"{name} {mark.when} [{mark.rule}] {kind(step)}: {steps.describe(step)}"
