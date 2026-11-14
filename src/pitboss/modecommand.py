"""The commands and actions that ask nothing of the decisions (keyword: one-path).

``Command`` and ``SlotsCommand`` are closed enumerations of their words, and each
member is a constructor of ``mode.Mode`` of its own (plan 6.1: one for each command
and action), so a match names the member it handles and ends in ``assert_never``. A
new command has no mode until it is named here or given a constructor of
``mode.Mode``; ``mode.parse`` exits 2 for any other (P4).
"""

import enum
from typing import Mapping


class Command(enum.Enum):
    """A command or action that asks nothing of the decisions, by its words.

    Attributes:
        ANALYZE_RED: ``analyze-red``.
        BASE_CHECK: ``base-check``.
        BODY_DIGEST: ``body-digest``.
        BODY_HEAD: ``body-head``.
        CANCEL_STALE_RUNS: ``cancel-stale-runs``.
        CAPTURE_TIMELINE: ``capture-timeline``.
        CASE_POST: ``case post``.
        CLAUSES_CHECK: ``clauses check``.
        CLEAN: ``clean``.
        CLEAN_CONTAINER: ``clean-container``.
        CLEAN_WORKTREES: ``clean-worktrees``.
        COUNT: ``count``.
        ENV_CHECK: ``env-check``.
        EXPAND: ``expand``.
        HAND_BACK_CHECK: ``hand-back-check``.
        HOOK: ``hook``.
        LINT: ``lint``.
        MERGED: ``merged``.
        NOX: ``nox``.
        OWNER_PAUSE: ``owner-pause``.
        PLAN_CHECK: ``plan-check``.
        PLAN_DIGEST: ``plan-digest``.
        PRESSURE: ``pressure``.
        PUSH: ``push``.
        QUEUED: ``queued``.
        QUIESCE: ``quiesce``.
        REVIEW_FORM: ``review-form``.
        RULES_CHECK: ``rules check``.
        RULING_POST: ``ruling post``.
        RULING_SUMMARY: ``ruling-summary``.
        STATUS_PROMPT: ``status-prompt``.
        SYNC: ``sync``.
        WORKER_ACTIONS: ``worker-actions``.
    """

    ANALYZE_RED = "analyze-red"
    BASE_CHECK = "base-check"
    BODY_DIGEST = "body-digest"
    BODY_HEAD = "body-head"
    CANCEL_STALE_RUNS = "cancel-stale-runs"
    CAPTURE_TIMELINE = "capture-timeline"
    CASE_POST = "case post"
    CLAUSES_CHECK = "clauses check"
    CLEAN = "clean"
    CLEAN_CONTAINER = "clean-container"
    CLEAN_WORKTREES = "clean-worktrees"
    COUNT = "count"
    ENV_CHECK = "env-check"
    EXPAND = "expand"
    HAND_BACK_CHECK = "hand-back-check"
    HOOK = "hook"
    LINT = "lint"
    MERGED = "merged"
    NOX = "nox"
    OWNER_PAUSE = "owner-pause"
    PLAN_CHECK = "plan-check"
    PLAN_DIGEST = "plan-digest"
    PRESSURE = "pressure"
    PUSH = "push"
    QUEUED = "queued"
    QUIESCE = "quiesce"
    REVIEW_FORM = "review-form"
    RULES_CHECK = "rules check"
    RULING_POST = "ruling post"
    RULING_SUMMARY = "ruling-summary"
    STATUS_PROMPT = "status-prompt"
    SYNC = "sync"
    WORKER_ACTIONS = "worker-actions"


class SlotsCommand(enum.Enum):
    """An action of ``slots`` that asks nothing of the decisions, by its words.

    Attributes:
        ADD: ``slots add``.
        CHECK: ``slots check``.
        CHECKIN: ``slots checkin``.
        DEVIATION: ``slots deviation``.
        FAILED: ``slots failed``.
        REMOVE: ``slots remove``.
        REPORT: ``slots report``.
        RESUME: ``slots resume``.
        SET: ``slots set``.
        SHOW: ``slots show``.
        TIME: ``slots time``.
        WAIT: ``slots wait``.
    """

    ADD = "slots add"
    CHECK = "slots check"
    CHECKIN = "slots checkin"
    DEVIATION = "slots deviation"
    FAILED = "slots failed"
    REMOVE = "slots remove"
    REPORT = "slots report"
    RESUME = "slots resume"
    SET = "slots set"
    SHOW = "slots show"
    TIME = "slots time"
    WAIT = "slots wait"


Unasked = Command | SlotsCommand  # each member is a mode of its own (plan 6.1)
UNASKED: Mapping[str, Unasked] = {
    each.value: each for kind in (Command, SlotsCommand) for each in kind
}
