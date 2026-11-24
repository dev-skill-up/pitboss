"""The e2e run of a draft whose changed e2e suite ran in no check run (run-e2e)."""

from typing import Sequence

from . import shapes, steps


def e2e_step(
    needs: bool, checks: Sequence[shapes.CheckRun], branch: str
) -> steps.Move | None:
    """The step of a draft whose changed e2e suite has run in no check run.

    A draft's CI skips the e2e jobs, so an approval of it reads no e2e result
    (keyword: run-e2e, pitboss#199). The check workflow is dispatched on its
    branch, and its run is the check run the approval waits for. A draft's own
    completed run does not end the step (it skipped e2e, the case of the
    ticket); only a dispatched run of ``check.yml`` at the head that completed does.

    Args:
        needs: whether the draft's diff touches a path the e2e suite runs on.
        checks: the check runs of its head.
        branch: its head branch.

    Returns:
        None when its diff touches no path the e2e suite runs on or a
        dispatched run of the head completed; the wait for CI when a check run
        of the head has started and not finished (it is not dispatched again);
        else the dispatch.
    """
    if not needs:
        return None
    running = [each for each in checks if not each.finished]
    return steps.Idle.CI_RUN if running else steps.run_e2e(branch)
