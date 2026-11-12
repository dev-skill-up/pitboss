"""Replaying a captured timeline at a moment of it (keyword: scenario, pitboss#444).

``pitboss capture-timeline`` writes what GitHub recorded of a real PR. ``state_at``
gives the ``PullState`` the flow would have read at a time: the comments, reviews,
label and draft events and check runs up to it, and the head the newest commit
made. The PR's body is its final text, since GitHub keeps no history of a body,
and the merge state is clean: a mark is placed where those two hold.
"""

import dataclasses
import json
import pathlib
from typing import Any, Mapping, Sequence

from .. import config, flow, parsing, reviews, steps

DIRECTORY = pathlib.Path(__file__).parent / "scenarios"
FORM = config.ReviewForm(
    lines=("Independent review (a separate reviewer agent, not the author) of head {sha}: {verdict}",),
    approved="approved",
    changes_needed="changes needed",
)
REVIEW = config.Review(
    trusted=frozenset({"OWNER", "MEMBER", "COLLABORATOR"}),
    gated=frozenset(),
    form=FORM,
    gated_form=FORM,
)


@dataclasses.dataclass(frozen=True, slots=True)
class Mark:
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


def load(name: str) -> Mapping[str, Any]:
    """Read a captured timeline.

    Args:
        name: the file's name in ``scenarios`` without ``.json``
            (``dev-skill-up-pitboss-465``).

    Returns:
        The timeline.
    """
    text = (DIRECTORY / f"{name}.json").read_text(encoding="utf-8")
    return json.loads(text)


def labels_at(data: Mapping[str, Any], when: str) -> frozenset[str]:
    """The labels the PR carried at a time.

    Args:
        data: the timeline.
        when: the time.

    Returns:
        The label names after the events up to ``when``.
    """
    named: set[str] = set()
    for each in data["events"]:
        if each["created_at"] <= when and each["event"] == "labeled":
            named.add(each["label"])
        if each["created_at"] <= when and each["event"] == "unlabeled":
            named.discard(each["label"])
    return frozenset(named)


def draft_at(data: Mapping[str, Any], when: str) -> bool:
    """Whether the PR was a draft at a time.

    Args:
        data: the timeline.
        when: the time.

    Returns:
        The state after the draft events up to ``when``; before any, the state
        the first event leaves (a PR made ready began as a draft).
    """
    marks = [each for each in data["events"] if each["event"] in _DRAFTING]
    state = bool(marks) and marks[0]["event"] == "ready_for_review"
    if not marks:
        state = bool(data["pull"]["draft"])
    for each in marks:
        if each["created_at"] <= when:
            state = each["event"] == "convert_to_draft"
    return state


_DRAFTING = ("ready_for_review", "convert_to_draft")


def head_at(data: Mapping[str, Any], when: str) -> str:
    """The sha of the head at a time.

    Args:
        data: the timeline.
        when: the time.

    Returns:
        The newest commit made by then (the first when none was).
    """
    made = [each for each in data["commits"] if each["date"] <= when]
    return (made or data["commits"])[-1 if made else 0]["sha"]


def _checks(
    data: Mapping[str, Any], head: str, when: str, settled: bool
) -> Sequence[Any]:
    runs = []
    for each in data["checks"].get(head, ()):
        if (each["started_at"] or "") > when:
            continue
        done = settled or (each["completed_at"] and each["completed_at"] <= when)
        runs.append(
            {
                **each,
                "status": each["status"] if done else "in_progress",
                "conclusion": each["conclusion"] if done else None,
            }
        )
    return parsing.check_runs(json.dumps({"check_runs": runs}))


def state_at(
    data: Mapping[str, Any], when: str, settled: bool = False
) -> flow.PullState:
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
    head = head_at(data, when)
    pull = {
        **data["pull"],
        "head": {"sha": head, "ref": data["pull"]["head"]["ref"]},
        "draft": draft_at(data, when),
        "mergeable_state": "clean",
    }
    comments = [each for each in data["comments"] if each["created_at"] <= when]
    posted = reviews.Sources(
        comments=parsing.comments(json.dumps(comments)),
        reviews=parsing.reviews(
            json.dumps(
                [each for each in data["reviews"] if each["submitted_at"] <= when]
            )
        ),
    )
    return flow.PullState(
        pull=parsing.pull(json.dumps(pull)),
        labels=labels_at(data, when),
        checks=_checks(data, head, when, settled),
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


def step_at(
    data: Mapping[str, Any], when: str, settled: bool = False
) -> steps.Next:
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
    """The line a scenario prints at a mark: what the flow gives and what is required.

    Args:
        name: the timeline's name.
        mark: the mark.

    Returns:
        The line, with the step ``steps.describe`` says.
    """
    step = step_at(load(name), mark.when, mark.settled)
    return f"{name} {mark.when} [{mark.rule}] {kind(step)}: {steps.describe(step)}"


def moments(data: Mapping[str, Any]) -> Sequence[str]:
    """Every time something happened to the PR, oldest first.

    Args:
        data: the timeline.

    Returns:
        The times of its comments, reviews, events and commits.
    """
    times = [each["created_at"] for each in data["comments"]]
    times += [each["created_at"] for each in data["events"]]
    times += [each["date"] for each in data["commits"]]
    times += [each["submitted_at"] for each in data["reviews"]]
    return sorted(set(times))
