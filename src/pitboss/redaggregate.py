"""The report's parts over the whole window: causes, costs, synthesis, tickets."""

from typing import Mapping, Sequence

from . import redmodel, redtext, redtickets


def _urls(report: redmodel.Report) -> dict[int, str]:
    return {each.facts.run.id: each.facts.run.url for each in report.pages}


def _burst_table(report: redmodel.Report) -> Sequence[str]:
    urls = _urls(report)
    return [
        "| Burst | Runs | Signature |",
        "| --- | --- | --- |",
        *(
            f"| {each.number} | {redtext.run_list(each.runs, urls)}"
            f" | `{each.signature}` |"
            for each in report.bursts
        ),
        "",
    ]


def _class_table(report: redmodel.Report) -> Sequence[str]:
    total, causes = len(report.pages), len(report.bursts)
    return [
        "| Class | Runs | % of runs | Causes | % of causes | Note |",
        "| --- | --- | --- | --- | --- | --- |",
        *(
            f"| {kind.value} | {share.runs} | {redtext.percent(share.runs, total)}"
            f" | {share.causes} | {redtext.percent(share.causes, causes)}"
            f" | {'one burst' if share.one_burst else ''} |"
            for kind, share in report.shares.items()
        ),
        "",
    ]


def _causes(report: redmodel.Report) -> Sequence[str]:
    return [
        "### Causes",
        "",
        f"{len(report.pages)} red runs, {len(report.bursts)} distinct causes"
        " (bursts: the same step and error text within 6 hours, or the same PR)."
        " Every percentage is given by run and by cause; a burst with runs of two"
        " classes counts in both.",
        "",
        *_burst_table(report),
        *_class_table(report),
    ]


def _largest(report: redmodel.Report) -> Sequence[str]:
    return [
        "| Largest runs | Failed job-min | Class |",
        "| --- | --- | --- |",
        *(
            f"| {redtext.run_ref(each.facts.run)}"
            f" | {redtext.minutes(each.cost.failed_seconds)}"
            f" | {each.classification.red_class.value} |"
            for each in report.costs.largest
        ),
        "",
    ]


def _per_class(report: redmodel.Report) -> Sequence[str]:
    return [
        "| Class | Failed job-min |",
        "| --- | --- |",
        *(
            f"| {kind.value} | {redtext.minutes(seconds)} |"
            for kind, seconds in report.costs.by_class.items()
        ),
        "",
        "| PR or branch | Full CI runs after its first red |",
        "| --- | --- |",
        *(f"| {name} | {count} |" for name, count in report.costs.extra_runs.items()),
        "",
    ]


def _costs(report: redmodel.Report) -> Sequence[str]:
    costs = report.costs
    return [
        "### Costs",
        "",
        f"Total failed job-minutes: {redtext.minutes(costs.failed_seconds)}.",
        "",
        *_largest(report),
        *_per_class(report),
        f"Red to fix push: {redtext.spread_text(costs.fix_push)}.",
        f"Fix push to green: {redtext.spread_text(costs.fix_to_green)}.",
        "Hours red (red to next green on the branch; this is the scheduling"
        f" measure, not the fix): {redtext.spread_text(costs.red_to_green)}.",
        "",
    ]


def summary_extra(report: redmodel.Report) -> Sequence[str]:
    """The causes and the costs, after the summary table.

    Args:
        report: the report.

    Returns:
        The Markdown lines.
    """
    return [*_causes(report), *_costs(report)]


def _effect(change: redmodel.Change, urls: Mapping[int, str]) -> str:
    if change.fix_path:
        return (
            "CI showed the failure after"
            f" {redtext.duration(change.detection_seconds)}, faster than the"
            f" mechanism costs ({redtext.duration(change.mechanism.cost_seconds)}),"
            " so the cost was the fix latency (median red to fix push"
            f" {redtext.duration(change.fix_push_seconds)}): the change is to the"
            " fix path, not to detection."
        )
    removed = redtext.run_list(change.removes, urls)
    return f"It would have removed these runs: {removed or 'none (not established)'}."


def _change_lines(
    number: int, change: redmodel.Change, urls: Mapping[int, str]
) -> Sequence[str]:
    return [
        f"{number}. Burst {change.burst} ({change.red_class.value}):"
        f" runs ({len(change.runs)}): {redtext.run_list(change.runs, urls)},"
        f" {redtext.minutes(change.failed_seconds)} failed job-minutes."
        f" Cheapest mechanism: {change.mechanism.text}.",
        f"   {_effect(change, urls)}",
        "   Open tickets it supersedes or is a piece of:"
        f" {redtext.ticket_list(change.tickets) or 'none'}.",
    ]


def synthesis_lines(report: redmodel.Report) -> Sequence[str]:
    """The synthesis: the changes with the most behind them.

    Args:
        report: the report.

    Returns:
        The Markdown lines.
    """
    urls = _urls(report)
    changes = (
        _change_lines(number, each, urls)
        for number, each in enumerate(report.changes, start=1)
    )
    return ["## Synthesis", "", *(text for lines in changes for text in lines), ""]


def _ticket_row(
    report: redmodel.Report, ticket: redtickets.Ticket, urls: Mapping[int, str]
) -> str:
    flag = (
        "cited by a red and still open a day later"
        if redtickets.open_a_day_after(ticket, report.now)
        else ""
    )
    name = redtext.link(f"{ticket.repo}#{ticket.number}", redtickets.url(ticket))
    return (
        f"| {name} {ticket.title} | {ticket.created_at}"
        f" | {redtext.run_list(ticket.cited, urls) or 'none'}"
        f" | {redtext.duration(redtickets.age_seconds(ticket))} | {flag} |"
    )


def ticket_lines(report: redmodel.Report) -> Sequence[str]:
    """The open p0 tickets, with the runs that cite each.

    Args:
        report: the report.

    Returns:
        The Markdown lines.
    """
    urls = _urls(report)
    return [
        "## Open p0 tickets",
        "",
        "| Ticket | Opened | Cited by runs | Age at first citation | Flag |",
        "| --- | --- | --- | --- | --- |",
        *(_ticket_row(report, each, urls) for each in report.tickets),
        "",
    ]
