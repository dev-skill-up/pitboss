"""What the caller reads for the questions only a draft asks (keyword: review-flow).

No import of the package: the flow reads these through ``flowstate``, and a
module with no import adds no level to the chain of modules the lint bounds.
"""

import dataclasses
from typing import Callable, Protocol, Sequence


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Draft:
    """What the caller reads for a draft.

    Attributes:
        needs_e2e: says whether the diff touches a path the e2e jobs run on and
            no dispatched run of ``check.yml`` at the head has completed (the
            caller reads the files, the configuration and the runs; a draft's
            own run skipped the e2e jobs, so it is not one; asked only for a
            draft whose Plan is approved; keyword: run-e2e).
        plan_review_check: the check a draft's Plan review waits for, empty
            when none (keyword: plan-review-check, pitboss#275).
        no_drafts: whether its repository has no drafts (keyword: no-drafts,
            pitboss#390).
    """

    needs_e2e: Callable[[], bool] = lambda: False
    plan_review_check: str = ""
    no_drafts: bool = False


class Run(Protocol):
    """A check run, as far as ``completed`` reads it (``shapes.CheckRun``)."""

    @property
    def name(self) -> str:
        """Its name.

        Returns:
            The value.
        """

    @property
    def finished(self) -> bool:
        """Whether it completed.

        Returns:
            The value.
        """


def completed(checks: Sequence[Run], name: str) -> bool:
    """Whether the check run of a name has completed (keyword: plan-review-check).

    A job of a called workflow is named ``caller / job``, so the name matches
    that form too.

    Args:
        checks: the current check runs of the head.
        name: the check's name.

    Returns:
        True when a run of that name completed, green or red; False when it
        runs, is queued or has not been created.
    """
    return any(
        each.finished and (each.name == name or each.name.endswith(f" / {name}"))
        for each in checks
    )
