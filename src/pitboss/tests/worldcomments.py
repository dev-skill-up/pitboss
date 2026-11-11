"""The comments of the PRs of a world (keyword: plan-check-always)."""

CLEAN_CHECK = {
    "body": "Plan check\nPlan digest: afbee19f3c5134c8\nPlan check: ok\n",
    "author_association": "MEMBER",
    "created_at": "2026-10-01T00:00:01Z",
}
REVIEW = {
    "body": f"## Review\nReviewed: {'a' * 40}\nVerdict: approved\n",
    "author_association": "MEMBER",
    "created_at": "2026-10-02T00:00:00Z",
}
COMMENTS = ([CLEAN_CHECK], [REVIEW, CLEAN_CHECK])
