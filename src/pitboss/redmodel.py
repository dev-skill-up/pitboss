"""The report as data: every red run's page, the bursts, the costs, the changes."""

import dataclasses
from typing import Mapping, Sequence

from . import redbursts, redclass, redcost, redshapes, redtickets, redtranscripts
from .red import Analysis
from .redshapes import RedClass


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Page:
    """Everything the report says about one red run.

    Attributes:
        facts: what GitHub says.
        signature: the key reds of one cause share.
        sharing: how many reds in the window have this signature.
        burst: the number of its burst.
        classification: its class and what decides it.
        cost: its cost line.
        local: what the pushing worker ran, from the transcripts.
        citing: the open tickets that cite this run.
    """

    facts: redshapes.RunFacts
    signature: str
    sharing: int
    burst: int
    classification: redclass.Classification
    cost: redcost.RunCost
    local: redtranscripts.LocalRuns
    citing: Sequence[redtickets.Ticket]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class ClassShare:
    """How much of the window a class is, by run and by cause.

    Attributes:
        runs: red runs of the class.
        causes: bursts holding a run of the class.
        one_burst: whether all of the class's runs are one burst.
    """

    runs: int
    causes: int
    one_burst: bool


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Costs:
    """The window's costs, computed.

    Attributes:
        failed_seconds: total failed job seconds.
        largest: the pages of the runs with the most failed job seconds.
        by_class: failed job seconds of each class.
        extra_runs: for each PR (or branch), the full runs after its first red.
        fix_push: seconds from the red to the fix push.
        fix_to_green: seconds from the fix push to green.
        red_to_green: seconds from the red to green (the scheduling measure).
    """

    failed_seconds: int
    largest: Sequence[Page]
    by_class: Mapping[RedClass, int]
    extra_runs: Mapping[str, int]
    fix_push: redcost.Spread | None
    fix_to_green: redcost.Spread | None
    red_to_green: redcost.Spread | None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Mechanism:
    """The cheapest thing that removes a class of reds.

    Attributes:
        text: what it is.
        cost_seconds: what it costs a run (the tool's fixed figure).
    """

    text: str
    cost_seconds: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Change:
    """One proposed change, with the runs behind it.

    Attributes:
        burst: the burst it comes from.
        red_class: the class of the burst.
        runs: the ids of the burst's runs.
        failed_seconds: their failed job seconds.
        mechanism: the cheapest mechanism for the class.
        detection_seconds: the median seconds CI took to show the failure.
        fix_path: whether the change is to the fix path (detection was
            faster than the mechanism, so the cost was the fix latency).
        removes: the runs the mechanism would have removed.
        fix_push_seconds: the median seconds from red to fix push.
        tickets: the open tickets that cite its runs.
    """

    burst: int
    red_class: RedClass
    runs: Sequence[int]
    failed_seconds: int
    mechanism: Mechanism
    detection_seconds: int
    fix_path: bool
    removes: Sequence[int]
    fix_push_seconds: int | None
    tickets: Sequence[redtickets.Ticket]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Report:
    """The whole report.

    Attributes:
        analysis: the window and its red runs.
        now: when it was made (ISO 8601).
        pages: a page for each red run, earliest first.
        bursts: the bursts.
        shares: each class's share.
        costs: the window's costs.
        changes: the synthesis.
        tickets: the open p0 tickets.
        transcripts: how many transcripts were searched.
    """

    analysis: Analysis
    now: str
    pages: Sequence[Page]
    bursts: Sequence[redbursts.Burst]
    shares: Mapping[RedClass, ClassShare]
    costs: Costs
    changes: Sequence[Change]
    tickets: Sequence[redtickets.Ticket]
    transcripts: int
