"""A runner hold withholds the sweep's lines that ask for a covered action too.

(keyword: hold-gate, quire#1110.) ``slots next`` offered the re-arm of an
auto-merge during a quiet period of the hold: the step ``MERGE`` was held
(``flow.next_step``), but the sweep's own lines (``READY TO MERGE``,
``AUTO MERGE OFF``, a merge by hand, the update of a branch that is behind and the
re-arm of a removal) were not. Each such line is one of the actions of
the gated actions of ``actiongates`` (hold); while ``signals.hold()`` is true they are
replaced by one
``WAIT-FOR-HOLD`` line that names what is withheld.
"""

from typing import TYPE_CHECKING, Mapping, Sequence

from . import pullref
from .markers import Marker

if TYPE_CHECKING:  # pragma: no cover
    from . import pulls

# keyword: hold-actions (pitboss#200): the one text of the actions a runner hold
# covers; the skill's references/ci.md ("What costs runs") quotes it word for word.
HOLD_ACTIONS = (
    "HOLD pushes to non-draft PRs, undrafts, enqueues, merges,"
    " workflow dispatches (a dispatch on a draft too) and re-runs"
    " (pushes to drafts are free)"
)

ASKED: Mapping[Marker, str] = {
    Marker.READY_TO_MERGE: "arm auto-merge or merge",
    Marker.AUTO_MERGE_OFF: "arm auto-merge again",
    Marker.MERGE_BY_HAND: "the merge",
    Marker.BEHIND: "the push that updates the branch",
}
PREFIXES = tuple(each.text for each in ASKED)


def _asked(line: str) -> str:
    return next(
        words for marker, words in ASKED.items() if line.startswith(marker.text)
    )


def gate(pull: "pulls.PullFacts", lines: Sequence[str]) -> Sequence[str]:
    """The lines of a PR, with the covered actions withheld while a hold lasts.

    Args:
        pull: the PR.
        lines: the lines it calls for.

    Returns:
        The lines unchanged when no hold covers the PR; else the lines that ask
        for no covered action, then one ``WAIT-FOR-HOLD`` line naming those that
        were withheld.
    """
    withheld = [each for each in lines if each.startswith(PREFIXES)]
    if not withheld or not pull.signals.hold():
        return lines
    kept = [each for each in lines if each not in withheld]
    what = ", ".join(_asked(each) for each in withheld)
    waiting = (
        f"{Marker.WAIT_FOR_HOLD.text} {pullref.reference(pull)}: a runner-pressure hold"
        f" or its quiet period withholds {what}; wait until `pitboss pressure` is clear"
    )
    return [*kept, waiting]
