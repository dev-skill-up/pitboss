"""The sentence of the Execution reviews about the repository's checklist (pitboss#438).

Like those of ``brieftext``, it is pinned by tests, so a change to it is a
reviewed code change.
"""

PRCHECK_REVIEW = (
    "Checklist: in a checkout of {repo} at the head, run `bats prcheck"
    " --checklist` and state each line of its output in the review, as"
    " `checked, ok` or as a finding (keyword: prcheck-checklist, pitboss#438)."
)
