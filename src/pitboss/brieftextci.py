"""The sentences of the briefs about what CI shows (pitboss#179).

Like those of ``brieftext``, they are pinned by tests, so a change to them is a
reviewed code change.
"""

from . import noxrow

PLAN_NO_NOX_ROW = noxrow.SENTENCE  # keyword: plan-nox (pitboss#251)
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
PLAN_NO_LOOP_REVIEW = (
    "Repeated runs: a Plan whose evidence is a repeated local run (a loop of N"
    " runs of a check) is a long run, which CI is the evidence for; it is changes"
    " needed, and the finding is `move the evidence to CI` (pitboss#288)."
)
PLAN_POINTER_LAST = (
    "Number the Plan rows with every command row first and the CI-pointer rows"
    " last; plan-row pairs the Nth Evidence command with row N (pitboss#274)."
)
PLAN_CI_POINTER = (
    "CI pointer: a Plan row whose result a CI run of the commit shows asks for no"
    " long local command (a whole suite or build, or anything over `timeout"
    " 598`); it points to CI and names the workflow, the step of the run's log, a"
    " greppable string that step prints (a test name or a line), and how the run"
    " is found for the commit (the run and job URL `actions` gives for the head)."
    " Evidence in the PR body is only for what CI does not show (pitboss#179)."
)
PLAN_ROWS = (PLAN_NO_NOX_ROW, PLAN_CI_POINTER, PLAN_POINTER_LAST)
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
REVIEW_CI_ACCEPTED = (
    "CI evidence in the body: for a row the Plan points to CI, a CI pointer (the"
    " workflow, the job URL of the head, the step and the greppable string) is the"
    " evidence; never ask for quoted log lines or pasted CI output (pitboss#277)."
)
RULING_NO_CI_QUOTES = (
    "CI in the steps: a ruling's steps never ask for CI log lines or pasted CI"
    " output in the PR body; they point to the run (the workflow, the job URL of"
    " the head, the step and the greppable string), as the CI pointer rule says"
    " (pitboss#277)."
)
E2E = (
    "E2E: this PR's diff touches what the e2e suite runs on. Read the run of"
    " `check.yml` of the head that ran e2e, and every e2e job of it: for a draft,"
    " whose CI skips e2e, the run dispatched on its branch (`RUN E2E BEFORE"
    " APPROVAL`). A head with no complete run is `NOT STARTED: e2e has not run at"
    " {head}`, not a verdict (pitboss#199)."
)
