"""The sentences of the briefs about what CI shows (pitboss#179).

Like those of ``brieftext``, they are pinned by tests, so a change to them is a
reviewed code change.
"""

PLAN_NO_NOX = (
    "CI evidence: the Plan never names `pitboss nox` or any nox run as its"
    " evidence (pitboss#179: a Plan asks for no evidence that CI shows); the whole"
    " suite is CI's `Run Nox` step, which the Plan points to as the CI pointer"
    " rule says."
)
PLAN_NO_NOX_REVIEW = (
    "CI evidence: a Plan that names `pitboss nox` or any nox run as its evidence"
    " is changes needed (pitboss#179: a Plan asks for no evidence that CI shows);"
    " the whole suite is CI's `Run Nox` step."
)
PLAN_CI_POINTER = (
    "CI pointer: a Plan row whose result a CI run of the commit shows asks for no"
    " long local command (a whole suite or build, or anything over `timeout"
    " 598`); it points to CI and names the workflow, the step of the run's log, a"
    " greppable string that step prints (a test name or a line), and how the run"
    " is found for the commit (the run and job URL `actions` gives for the head)."
    " Evidence in the PR body is only for what CI does not show (pitboss#179)."
)
BODY_CI_POINTER = (
    "CI in the body: for a row the Plan points to CI, the PR body gives no"
    " evidence and holds only the pointer, with the run and job URL found for the"
    " head, the workflow, the step and the greppable string; evidence in the PR"
    " body is only for what CI does not show (pitboss#179)."
)
PLAN_CI_POINTER_REVIEW = (
    "CI pointer: a Plan row that asks for a long local command (a whole suite or"
    " build, or anything over `timeout 598`) whose result a CI run of the commit"
    " shows is changes needed; so is a row that points to CI without the"
    " workflow, the step, a greppable string and how the run is found for the"
    " commit (pitboss#179)."
)
