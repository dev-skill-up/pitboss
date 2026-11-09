"""The sentence of the brief that resolves a conflict (pitboss#208).

Like those of ``brieftext``, it is pinned by tests, so a change to it is a
reviewed code change.
"""

CONFLICT_BODY = (
    "Conflict body: when the PR has a Plan or Execution body, after the merge set"
    " the last `Head:` line of the body to the merge head and rerun the Plan's"
    " commands through `uvx pitboss expand` at that head, replacing the Evidence"
    " (the body only, no other change); `uvx pitboss lint pr-body` refuses a body"
    " whose last `Head:` line is not the head of the PR."
)
