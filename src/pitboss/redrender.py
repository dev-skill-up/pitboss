"""The report as Markdown: summary, synthesis, pages, tickets."""

from typing import Sequence

from . import redmodel, redprompt, redsynth, redtext, redtickets
from .red import Analysis, describe
from .redshapes import RedClass
from .redaggregate import summary_extra, synthesis_lines, ticket_lines

READ_ONLY = (
    "This report is read-only on GitHub: it only reads (`gh api` GETs) and"
    " changes nothing there. What needs judgement is left to the prompt on"
    " each page, filled with the facts gathered."
)
SHOWN_COMMANDS = 30


def _summary_row(analysis: Analysis, page: redmodel.Page) -> str:
    run = page.facts.run
    branch = run.branch.replace("|", "\\|")
    return (
        f"| {redtext.run_ref(run)} | {redtext.run_pulls(analysis.repo, run)}"
        f" | {branch} | {redtext.commit_ref(analysis.repo, run.head_sha)}"
        f" | {run.conclusion} | {run.created_at}"
        f" | {page.classification.red_class.value}"
        f" | {redtext.minutes(page.cost.failed_seconds)} | {page.burst} |"
    )


def _summary(report: redmodel.Report) -> Sequence[str]:
    return [
        "## Summary",
        "",
        "| Run | PR | Branch | Commit | Conclusion | Started | Class"
        " | Failed job-min | Burst |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *(_summary_row(report.analysis, page) for page in report.pages),
        "",
        *summary_extra(report),
    ]


def _detector(page: redmodel.Page) -> str:
    run = page.facts.run
    if run.event == "merge_group":
        return f"the merge queue (event merge_group, run {redtext.run_ref(run)})"
    return (
        f"CI (event {run.event}, run {redtext.run_ref(run)}, ended"
        f" {run.updated_at}); whether the orchestrator's sweep or a human saw it"
        " first is step 3 of the prompt"
    )


def _error_lines(page: redmodel.Page) -> Sequence[str]:
    error = page.facts.error
    if error is None:
        return [f"First error line: none, because {page.facts.log_note}."]
    step = error.step
    lines = [
        f"Failing job and step: {redtext.job_ref(error.job)}, step {step.number}"
        f" `{step.name}`, {step.started_at} to {step.completed_at}"
        f" (job {error.job.started_at} to {error.job.completed_at}).",
        f"First error line (log line {error.line} of job {error.job.id}):"
        f" `{error.text}`",
    ]
    if error.inferred_from:
        lines.append(
            f"Cause inferred from run {error.inferred_from}: same commit, same"
            " failing step; this run's own log was not readable."
        )
    return lines


def _after_lines(page: redmodel.Page) -> Sequence[str]:
    facts = page.facts
    later = facts.later[0] if facts.later else None
    after = "none"
    if later is not None:
        after = (
            f"{redtext.run_ref(later)} ({later.created_at}),"
            f" {later.conclusion or 'not finished'}"
        )
    went = "went green" if page.cost.went_green else "never went green"
    pull = facts.pull
    if pull is None:
        merged = "no PR is tied to this run"
    else:
        state = "merged" if pull.merged else f"not merged (it is {pull.state})"
        merged = f"{redtext.link('PR #' + str(pull.number), pull.url)} {state}"
    return [f"Next run on the branch: {after}. The branch {went}; {merged}."]


def _local_lines(report: redmodel.Report, page: redmodel.Page) -> Sequence[str]:
    local, run = page.local, page.facts.run
    commit = redtext.commit_ref(report.analysis.repo, run.head_sha)
    if not local.found:
        return [
            f"Pushing worker's transcript: not found for the push of {commit} on"
            f" `{run.branch}` (searched {local.searched} transcripts); what the"
            " worker ran locally is not known."
        ]
    shown = [
        f"  - {redtext.command_line(each)}" for each in local.commands[:SHOWN_COMMANDS]
    ]
    more = len(local.commands) - len(shown)
    return [
        f"Pushing worker's transcript: agent `{local.agent}`. Commands run"
        f" before the push ({len(local.commands)}):",
        *shown,
        *([f"  - ... and {more} more"] if more > 0 else []),
        f"Failing names found among those commands: {', '.join(local.ran) or 'none'};"
        f" not found: {', '.join(local.not_ran) or 'none'}.",
    ]


def _fix_lines(report: redmodel.Report, page: redmodel.Page) -> Sequence[str]:
    fix, cost = page.facts.fix, page.cost
    if fix is None:
        return [f"Fix: none pushed. Verification: {cost.verification.value}."]
    first = fix.message.splitlines()[0] if fix.message else ""
    files = ", ".join(f"`{name}`" for name in fix.files[:10]) or "none"
    return [
        f"Fix commit {redtext.commit_ref(report.analysis.repo, fix.sha)} ({fix.date}):"
        f" {first}; files: {files}. Verification: {cost.verification.value}."
    ]


def _cost_line(page: redmodel.Page) -> str:
    cost = page.cost
    green = "" if cost.went_green else " (it never went green)"
    return (
        f"Cost: {redtext.minutes(cost.failed_seconds)} failed job-minutes; "
        f"{cost.extra_runs} full CI runs on the branch after this red{green}; "
        f"red to fix push {redtext.duration(cost.fix_push_seconds)}; "
        f"fix push to green {redtext.duration(cost.fix_to_green_seconds)}; "
        f"red to green {redtext.duration(cost.red_to_green_seconds)} (the"
        " scheduling measure, not the fix)."
    )


def _known_bad(page: redmodel.Page) -> str:
    citing = redtext.ticket_list(page.citing)
    quarantine = redtickets.LABEL_NAMES[redtickets.Label.QUARANTINED]
    held = any(quarantine in each.labels for each in page.citing)
    return (
        f"Known-bad: {page.sharing} red(s) in the window share the signature"
        f" `{page.signature}`; tickets citing this run: {citing or 'none'};"
        f" quarantined: {'yes' if held else 'no'} (label `{quarantine}`)."
    )


def _first_detector(page: redmodel.Page) -> str:
    red_class = page.classification.red_class
    mechanism = redsynth.MECHANISMS[red_class]
    seen = redtext.duration(page.cost.detection_seconds)
    verdict = (
        "CI was faster than that, so the cost was the fix latency"
        if mechanism.cost_seconds > page.cost.detection_seconds
        else "cheaper than CI's detection"
    )
    return (
        f"First detector that could have caught it: {mechanism.text} (the tool's"
        f" fixed cost {redtext.duration(mechanism.cost_seconds)}; CI showed the"
        f" failure after {seen}: {verdict})."
    )


def _class_line(page: redmodel.Page) -> str:
    classification = page.classification
    established = (
        "not established"
        if classification.red_class is RedClass.NOT_ESTABLISHED
        else "established by a rule"
    )
    return (
        f"Class: {classification.red_class.value} ({established}:"
        f" {classification.basis})."
    )


def facts_lines(report: redmodel.Report, page: redmodel.Page) -> Sequence[str]:
    """The facts of a page, one line each.

    Args:
        report: the report.
        page: the page.

    Returns:
        The lines (the prompt carries the same ones).
    """
    run, repo = page.facts.run, report.analysis.repo
    return [
        f"Run {redtext.run_ref(run)}: {run.conclusion}, branch `{run.branch}`,"
        f" commit {redtext.commit_ref(repo, run.head_sha)}, PR"
        f" {redtext.run_pulls(repo, run)}, started {run.created_at}.",
        *_error_lines(page),
        _class_line(page),
        f"Detected by: {_detector(page)}.",
        *_local_lines(report, page),
        *_after_lines(page),
        _cost_line(page),
        *_fix_lines(report, page),
        _known_bad(page),
        _first_detector(page),
    ]


def _page(report: redmodel.Report, page: redmodel.Page) -> Sequence[str]:
    lines = facts_lines(report, page)
    repo = report.analysis.repo.slug
    prompt = redprompt.fill(report.analysis.workflow, repo, lines)
    run = page.facts.run
    return [
        f"### Run {run.id}: {run.conclusion} on `{run.branch}`",
        "",
        redprompt.facts_block(lines),
        "",
        "Prompt for the judgement items:",
        "",
        "~~~text",
        prompt.rstrip(),
        "~~~",
        "",
    ]


def _header(report: redmodel.Report) -> Sequence[str]:
    analysis = report.analysis
    return [
        f"# Red runs of {analysis.workflow} in {analysis.repo.slug}",
        "",
        READ_ONLY,
        "",
        f"Window: {describe(analysis.window)}: {analysis.total} runs,"
        f" {len(analysis.reds)} red. Made {report.now}. Transcripts searched:"
        f" {report.transcripts}.",
        "",
    ]


def render(report: redmodel.Report) -> str:
    """Write the report as Markdown.

    Args:
        report: the report.

    Returns:
        The report: the read-only note, the summary table, the synthesis, the
        pages, the tickets.
    """
    pages = (_page(report, each) for each in report.pages)
    lines = [
        *_header(report),
        *_summary(report),
        *synthesis_lines(report),
        "## Pages",
        "",
        *(line for lines_of_page in pages for line in lines_of_page),
        *ticket_lines(report),
    ]
    return "\n".join(lines)
