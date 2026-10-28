"""Building the whole report: every red run's page, the bursts, the costs."""

import collections
import concurrent.futures
import dataclasses
from typing import Callable, Mapping, Sequence

from . import (
    config,
    ghapi,
    redbursts,
    redclass,
    redcost,
    redgather,
    redlog,
    redmodel,
    redshapes,
    redsynth,
    redtickets,
    redtranscripts,
    shapes,
)
from .red import Analysis
from .redshapes import RedClass

NO_ERROR = "no error line"
LARGEST = 5


def signature_of(facts: redshapes.RunFacts) -> str:
    """The signature of a red run.

    Args:
        facts: its facts.

    Returns:
        The step and error text, or what the run lacks.
    """
    if facts.error is None:
        return redlog.signature(NO_ERROR, facts.log_note)
    return redlog.signature(facts.error.step.name, facts.error.text)


def _names(facts: redshapes.RunFacts) -> Sequence[str]:
    if facts.error is None:
        return []
    return [
        facts.error.job.name,
        facts.error.step.name,
        *redlog.error_files(facts.error.text),
    ]


def _shares(pages: Sequence[redmodel.Page]) -> Mapping[RedClass, redmodel.ClassShare]:
    members: dict[RedClass, set[int]] = {}
    counts: collections.Counter[RedClass] = collections.Counter()
    for each in pages:
        red_class = each.classification.red_class
        members.setdefault(red_class, set()).add(each.burst)
        counts[red_class] += 1
    return {
        red_class: redmodel.ClassShare(
            runs=counts[red_class],
            causes=len(bursts),
            one_burst=len(bursts) == 1,
        )
        for red_class, bursts in members.items()
    }


def _per_pull(pages: Sequence[redmodel.Page]) -> Mapping[str, int]:
    first: dict[str, redmodel.Page] = {}
    for each in pages:
        run = each.facts.run
        first.setdefault(f"#{run.pulls[0]}" if run.pulls else run.branch, each)
    return {key: each.cost.extra_runs for key, each in first.items()}


def _seconds(
    pages: Sequence[redmodel.Page],
    pick: Callable[[redcost.RunCost], int | None],
) -> redcost.Spread | None:
    values = [pick(each.cost) for each in pages]
    return redcost.distribution([value for value in values if value is not None])


def _costs(pages: Sequence[redmodel.Page]) -> redmodel.Costs:
    by_class: dict[RedClass, int] = collections.Counter()
    for each in pages:
        by_class[each.classification.red_class] += each.cost.failed_seconds
    largest = sorted(pages, key=lambda each: each.cost.failed_seconds, reverse=True)
    return redmodel.Costs(
        failed_seconds=sum(each.cost.failed_seconds for each in pages),
        largest=largest[:LARGEST],
        by_class=dict(by_class),
        extra_runs=_per_pull(pages),
        fix_push=_seconds(pages, lambda cost: cost.fix_push_seconds),
        fix_to_green=_seconds(pages, lambda cost: cost.fix_to_green_seconds),
        red_to_green=_seconds(pages, lambda cost: cost.red_to_green_seconds),
    )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Sources:
    """Where the report reads from.

    Attributes:
        github: the API (only read).
        repos: the repositories whose open p0 tickets are listed.
        transcripts: where the workers' transcripts are.
    """

    github: ghapi.GitHub
    repos: Sequence[config.Repo]
    transcripts: redtranscripts.Transcripts


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class _Context:
    counts: Mapping[str, int]
    burst_of: Mapping[int, int]
    tickets: Sequence[redtickets.Ticket]
    searched: redtranscripts.Searched


def _page(facts: redshapes.RunFacts, context: _Context) -> redmodel.Page:
    signature = signature_of(facts)
    sharing = context.counts[signature]
    citing = [each for each in context.tickets if facts.run.id in each.cited]
    run = facts.run
    return redmodel.Page(
        facts=facts,
        signature=signature,
        sharing=sharing,
        burst=context.burst_of[run.id],
        classification=redclass.classify(facts, sharing, citing),
        cost=redcost.run_cost(facts),
        local=redtranscripts.local_runs(
            context.searched, run.branch, run.head_sha, _names(facts)
        ),
        citing=citing,
    )


def _read_all(sources: Sources, analysis: Analysis) -> Sequence[redshapes.RunFacts]:
    def read(run: shapes.WindowRun) -> redshapes.RunFacts:
        return redgather.read_facts(
            sources.github, analysis.repo, analysis.workflow, run
        )

    with concurrent.futures.ThreadPoolExecutor() as pool:
        found = list(pool.map(read, analysis.reds))
    return sorted(redgather.infer(found), key=lambda each: each.run.created_at)


def _read_context(
    sources: Sources,
    facts: Sequence[redshapes.RunFacts],
    bursts: Sequence[redbursts.Burst],
) -> _Context:
    return _Context(
        counts=collections.Counter(signature_of(each) for each in facts),
        burst_of={run: burst.number for burst in bursts for run in burst.runs},
        tickets=redtickets.read_tickets(
            sources.github, sources.repos, [each.run.id for each in facts]
        ),
        searched=redtranscripts.search(
            sources.transcripts,
            [(each.run.branch, each.run.head_sha) for each in facts],
        ),
    )


def build(sources: Sources, analysis: Analysis, now: str) -> redmodel.Report:
    """Read everything about the red runs and compute the report.

    Args:
        sources: where to read from.
        analysis: the window and its red runs.
        now: the time now (ISO 8601).

    Returns:
        The report.
    """
    facts = _read_all(sources, analysis)
    bursts = redbursts.group(facts, {each.run.id: signature_of(each) for each in facts})
    context = _read_context(sources, facts, bursts)
    pages = [_page(each, context) for each in facts]
    return redmodel.Report(
        analysis=analysis,
        now=now,
        pages=pages,
        bursts=bursts,
        shares=_shares(pages),
        costs=_costs(pages),
        changes=redsynth.synthesize(bursts, pages),
        tickets=context.tickets,
        transcripts=context.searched.count,
    )
