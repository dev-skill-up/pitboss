"""What each step says, in one line (keyword: review-flow).

``describe`` is the verb of a decision; an idle PR has no words (one-path).
"""

import dataclasses
from typing import Mapping

from .steps import (
    OWNER_ARTIFACT,
    PAUSED_LABEL,
    PLAN_CHECK_FIRST_LINE,
    RULING_FIRST_LINE,
    RUN_E2E_MARKER,
    Next,
    Step,
)

TEXTS: Mapping[Step, str] = {
    Step.UNDRAFT: "mark the PR ready; the next step is the CI gate on the head",
    Step.OPUS_RULING: (
        "start an Opus agent whose only brief is to make a ruling, and record it"
        f" as a PR comment whose first line is {RULING_FIRST_LINE!r}"
    ),
    Step.PAUSE_FOR_OWNER: (
        f"label the PR and its ticket {PAUSED_LABEL}, comment what the rounds"
        " disagreed about, the options and a `How we got here` section, and report"
        " the number and the options to the owner on a card that has the section"
        f" and, on the card, {OWNER_ARTIFACT}"
    ),
    Step.FIX_RULING: (
        "the newest Opus ruling has no readable `Ruling:` second line; an agent"
        " edits or reposts the comment; no Opus agent is asked for"
    ),
    Step.RULING_ESCALATES: (
        "the Opus ruling escalated to the owner: label the PR and its ticket"
        f" {PAUSED_LABEL}, comment the options and a `How we got here` section,"
        " and report the number and the options to the owner on a card that has"
        f" the section and, on the card, {OWNER_ARTIFACT}"
    ),
    Step.PLAN_EDITED: (
        "the Plan was edited after its approval: restore the approved Plan, or"
        " ask an Opus agent for a ruling that says `revise the plan`; no review"
        " or fix is offered meanwhile"
    ),
    Step.PLAN_CHECK: (
        "post the Plan check: run `uvx pitboss plan-check <body file>` on the PR"
        " body and post its whole"
        f" output as a PR comment (its first line is {PLAN_CHECK_FIRST_LINE!r});"
        " the Plan review is offered once it says `Plan check: ok` for this Plan"
    ),
    Step.SEND_BACK_PLAN_CHECK: (
        "the Plan check is refused ({comment}): the worker that pushed the PR"
        " sends back the posted check; this is no fix round: {findings}"
    ),
    Step.RUN_E2E: f"{RUN_E2E_MARKER}: dispatch check.yml on {{branch}}",
    Step.MERGE: "CI is green and there is no conflict: arm auto-merge or merge",
}


# keyword: fixed-on-base (pitboss#314): the words of a red CI the base has answered
ENQUEUE = "enqueue it (the merge queue tests it on main)"
REQUEST_REVIEW = "request the review"


def describe(step: Next) -> str:
    """Say what to do for a step, in one line.

    Args:
        step: the step.

    Returns:
        Its task, its stage, or the text of the step.
    """
    if step.step is Step.MERGE and step.on_base:
        return ENQUEUE
    if step.task is not None and step.findings:  # what is missing, said with it
        return f"{step.task.value}: {step.findings}"
    if step.task is not None:
        return step.task.value
    if step.stage is not None and step.on_base:
        return f"{REQUEST_REVIEW}: {step.stage.value}"
    if step.stage is not None:
        return step.stage.value
    return TEXTS[step.step].format_map(dataclasses.asdict(step))
