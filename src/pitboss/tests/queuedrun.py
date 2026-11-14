"""A workflow run queued since 2026-11-12 (keyword: stuck-ci)."""

from .. import shapes

RUN = shapes.WorkflowRun(
    id=1,
    status="queued",
    conclusion=None,
    finished=False,
    created_at="2026-11-12T00:00:00Z",
    head_branch="b",
)
