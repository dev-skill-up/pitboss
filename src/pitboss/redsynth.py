"""The synthesis: the changes with the most job-minutes or runs behind them."""

import statistics
from typing import Mapping, Sequence

from . import redbursts, redmodel
from .redshapes import RedClass

CHANGES = 3


MECHANISMS: Mapping[RedClass, redmodel.Mechanism] = {
    RedClass.UNLISTED_FIXTURE: redmodel.Mechanism(
        text="a grouping check before push (every fixture is in a group)",
        cost_seconds=6,
    ),
    RedClass.STALE_ANCHOR_OR_EXPECT: redmodel.Mechanism(
        text="bless or run the changed fixtures' expects before push",
        cost_seconds=120,
    ),
    RedClass.LOCAL_ENVIRONMENT_DIFFERS: redmodel.Mechanism(
        text="run the test under CI's conditions before push (e.g. `sudo -n`)",
        cost_seconds=60,
    ),
    RedClass.PIN_MOVE: redmodel.Mechanism(
        text="a `needs: build` edge, so a pin move fails once, early",
        cost_seconds=0,
    ),
    RedClass.PRODUCT_CHANGE_BROKE_UNRUN_SPECS: redmodel.Mechanism(
        text="run the specs the changed files touch before push",
        cost_seconds=600,
    ),
    RedClass.KNOWN_BAD_TEST: redmodel.Mechanism(
        text="quarantine the test until its ticket is fixed", cost_seconds=0
    ),
    RedClass.NEW_TEST_WRONG_UNDER_CI: redmodel.Mechanism(
        text="run a new test under CI's conditions before it is pushed",
        cost_seconds=60,
    ),
    RedClass.EXTERNAL_INFRASTRUCTURE: redmodel.Mechanism(
        text="nothing: the service was down; cache it if it repeats",
        cost_seconds=0,
    ),
    RedClass.OWN_RELEASE_OR_CONFIGURATION_BUG: redmodel.Mechanism(
        text="a lint of the release configuration before push", cost_seconds=6
    ),
    RedClass.NOT_ESTABLISHED: redmodel.Mechanism(
        text="none until the cause is established (each page has its prompt)",
        cost_seconds=0,
    ),
}


def _change(burst: redbursts.Burst, pages: Sequence[redmodel.Page]) -> redmodel.Change:
    mine = [page for page in pages if page.burst == burst.number]
    red_class = mine[0].classification.red_class
    mechanism = MECHANISMS[red_class]
    detection = int(statistics.median(p.cost.detection_seconds for p in mine))
    fix_path = mechanism.cost_seconds > detection
    fixes = [p.cost.fix_push_seconds for p in mine if p.cost.fix_push_seconds]
    cited = {t.number: t for page in mine for t in page.citing}
    return redmodel.Change(
        burst=burst.number,
        red_class=red_class,
        runs=burst.runs,
        failed_seconds=sum(p.cost.failed_seconds for p in mine),
        mechanism=mechanism,
        detection_seconds=detection,
        fix_path=fix_path,
        removes=[] if fix_path or red_class is RedClass.NOT_ESTABLISHED else burst.runs,
        fix_push_seconds=int(statistics.median(fixes)) if fixes else None,
        tickets=list(cited.values()),
    )


def synthesize(
    bursts: Sequence[redbursts.Burst], pages: Sequence[redmodel.Page]
) -> Sequence[redmodel.Change]:
    """Name the changes with the largest job-minutes or run count behind them.

    A change that costs more than CI took to show the failure is not
    proposed. The burst's cost was then the fix latency, and the change is
    to the fix path.

    Args:
        bursts: the bursts.
        pages: every red run's page.

    Returns:
        At most three changes, the largest first.
    """
    changes = [_change(burst, pages) for burst in bursts]
    ranked = sorted(
        changes, key=lambda c: (c.failed_seconds, len(c.runs)), reverse=True
    )
    return ranked[:CHANGES]
