"""The commands and actions that ask nothing of the decisions (keyword: one-path).

``Command`` is a closed enumeration of their words, so a new command has no mode
until it is named here or given a constructor of ``mode.Mode``; ``mode.parse``
exits 2 for any other (P4).
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
        SLOTS_ADD: ``slots add``.
        SLOTS_CHECK: ``slots check``.
        SLOTS_CHECKIN: ``slots checkin``.
        SLOTS_DEVIATION: ``slots deviation``.
        SLOTS_FAILED: ``slots failed``.
        SLOTS_REMOVE: ``slots remove``.
        SLOTS_REPORT: ``slots report``.
        SLOTS_RESUME: ``slots resume``.
        SLOTS_SET: ``slots set``.
        SLOTS_SHOW: ``slots show``.
        SLOTS_TIME: ``slots time``.
        SLOTS_WAIT: ``slots wait``.
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
    SLOTS_ADD = "slots add"
    SLOTS_CHECK = "slots check"
    SLOTS_CHECKIN = "slots checkin"
    SLOTS_DEVIATION = "slots deviation"
    SLOTS_FAILED = "slots failed"
    SLOTS_REMOVE = "slots remove"
    SLOTS_REPORT = "slots report"
    SLOTS_RESUME = "slots resume"
    SLOTS_SET = "slots set"
    SLOTS_SHOW = "slots show"
    SLOTS_TIME = "slots time"
    SLOTS_WAIT = "slots wait"
    STATUS_PROMPT = "status-prompt"
    SYNC = "sync"
    WORKER_ACTIONS = "worker-actions"


UNASKED: Mapping[str, Command] = {each.value: each for each in Command}
