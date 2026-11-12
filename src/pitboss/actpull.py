"""The verbs that change a PR's state or the project's holds (keyword: act-verbs).

merge, arm and undraft run the verdict in the same call as the write; arm
records the head it armed; hold disarms and dequeues the PRs it covers; label
``paused-owner`` and block disarm the PR; override lifts one stop line at one
head, never a failed check or status, a hold, a block, a closed PR or a failed
read.
"""

from . import actcore, totalanswer
from .totaljson import text

LABELS = totalanswer.KNOWN_LABELS | {"p0", "p1", "p2", "p3", actcore.HOLD_LABEL}
WORKFLOWS = ("relock.yml", "check.yml")
CLOSE_REASONS = ("completed", "not_planned", "duplicate")
OVERRIDDEN = ("merge", "arm", "undraft")


def _gated_write(act: actcore.Act, action: str, target: actcore.Target) -> str:
    actcore.gate(act, action, target.repo)
    pull = actcore.verdict_of(act, action, target)
    if action == "arm":
        actcore.record(act, target, f"arm head={actcore.head_of(pull)}")
    act.hub.write(actcore.Change(kind=action, repo=target.repo, number=target.number))
    return f"{action} {target.repo}#{target.number} at {actcore.head_of(pull)}"


def merge(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Merge a PR when the verdict is GO.

    Args:
        act: the verb's world.
        target: the PR.
        options: none.

    Returns:
        What was done.
    """
    return _gated_write(act, "merge", target)


def arm(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Arm auto-merge when the verdict is GO, with a record of the head.

    Args:
        act: the verb's world.
        target: the PR.
        options: none.

    Returns:
        What was done.
    """
    return _gated_write(act, "arm", target)


def undraft(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Mark a draft ready when the verdict is GO.

    Args:
        act: the verb's world.
        target: the PR.
        options: none.

    Returns:
        What was done.
    """
    return _gated_write(act, "undraft", target)


def disarm(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Disarm auto-merge.

    Args:
        act: the verb's world.
        target: the PR.
        options: none.

    Returns:
        What was done.
    """
    actcore.gate(act, "disarm", target.repo)
    act.hub.write(actcore.Change(kind="disarm", repo=target.repo, number=target.number))
    return f"disarm {target.repo}#{target.number}"


def _stopped_head(act: actcore.Act, target: actcore.Target, stop: str) -> str:
    # the PR's head, when the stop line is one of the verdict's there
    pull = act.hub.pull(target.repo, target.number)
    events = act.hub.timeline(target.repo, target.number)
    ctx = act.inputs(target.repo, target.number, pull, events)
    said = [act.controls.verdict(each, pull, ctx).lines for each in OVERRIDDEN]
    if not any(stop in each for each in said):
        raise actcore.Refused(f"not a stop line of this head: {stop[:60]!r}")
    return actcore.head_of(pull)


def override_stop(
    act: actcore.Act, target: actcore.Target, options: actcore.Options
) -> str:
    """Lift one stop line for the PR's head, with a reason.

    Args:
        act: the verb's world.
        target: the PR.
        options: ``stop`` (the line) and ``reason`` (the ruling it rests on).

    Returns:
        What was done.

    Raises:
        actcore.Refused: the line is one no override lifts.
    """
    actcore.gate(act, "override", target.repo)
    stop, reason = actcore.option(options, "stop"), actcore.option(options, "reason")
    if stop.startswith(tuple(act.controls.not_overridable)):
        raise actcore.Refused(
            "a hold, a failed check or status, a block, a read failure or a closed PR"
            " is not overridable"
        )
    head = _stopped_head(act, target, stop)
    actcore.record(act, target, f'override head={head} stop="{stop}" reason="{reason}"')
    return f"override {target.repo}#{target.number} at {head}"


def block(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Record that a PR waits on another item; the verdict reads it.

    Args:
        act: the verb's world.
        target: the PR.
        options: ``on`` (``owner/name#N``).

    Returns:
        What was done.
    """
    actcore.gate(act, "block", target.repo)
    on = actcore.option(options, "on")
    act.controls.disarm(act, target, f"blocked by {on}")
    head = actcore.head_of(act.hub.pull(target.repo, target.number))
    actcore.record(act, target, f"blocked-by head={head} {on}")
    return f"block {target.repo}#{target.number} on {on}"


def label(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Add or remove a label pitboss applies; ``paused-owner`` disarms.

    Args:
        act: the verb's world.
        target: the PR or issue.
        options: ``name``, and ``remove`` to remove it.

    Returns:
        What was done.

    Raises:
        actcore.Refused: a label pitboss does not apply.
    """
    actcore.gate(act, "label", target.repo)
    name = actcore.option(options, "name")
    if name not in LABELS:
        raise actcore.Refused(f"label {name} is not one pitboss applies")
    removing = bool(options.get("remove"))
    if name == totalanswer.PAUSED and not removing:
        act.controls.disarm(act, target, totalanswer.PAUSED)
    kind = "unlabel" if removing else "label"
    act.hub.write(
        actcore.Change(
            kind=kind, repo=target.repo, number=target.number, fields={"name": name}
        )
    )
    return f"{kind} {name} on {target.repo}#{target.number}"


def hold(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Hold a scope in one repository or all; disarm and dequeue the PRs it covers.

    Args:
        act: the verb's world.
        target: the repository ("all" for every one of the project).
        options: ``scope`` (pushes, merges, undrafts, ci, dispatch, all) and
            ``source`` (the owner message it comes from).

    Returns:
        What was done.
    """
    actcore.gate(act, "hold", target.repo)
    return make_hold(
        act,
        target.repo,
        actcore.option(options, "scope"),
        actcore.option(options, "source"),
    )


def make_hold(act: actcore.Act, where: str, scope: str, source: str) -> str:
    """Make the hold issues and disarm and dequeue what the scope covers.

    Args:
        act: the verb's world.
        where: the repository, or "all".
        scope: the scope held.
        source: the owner message it comes from.

    Returns:
        What was done.
    """
    named = act.repos if where == "all" else [where]
    for each in named:
        fields = {
            "title": f"pitboss hold: {scope}",
            "body": f"scope={scope}\nfrom={source}",
            "labels": actcore.HOLD_LABEL,
        }
        act.hub.write(actcore.Change(kind="issue", repo=each, fields=fields))
        if scope in actcore.DISARMING:
            _disarm_all(act, each, f"hold {scope}")
    return f"hold {scope} in {', '.join(named)}"


def _disarm_all(act: actcore.Act, repo: str, why: str) -> None:
    for pull in act.hub.open_pulls(repo):
        number = pull.get("number")
        target = actcore.Target(
            repo=repo, number=number if isinstance(number, int) else 0
        )
        act.controls.disarm(act, target, why)


def unhold(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """End a hold (close its issue).

    Args:
        act: the verb's world.
        target: the hold's issue.
        options: none.

    Returns:
        What was done.
    """
    actcore.gate(act, "unhold", target.repo)
    act.hub.write(
        actcore.Change(
            kind="close-issue",
            repo=target.repo,
            number=target.number,
            fields={"reason": "completed"},
        )
    )
    return f"unhold {target.repo}#{target.number}"


def update_branch(
    act: actcore.Act, target: actcore.Target, options: actcore.Options
) -> str:
    """Merge the base into a PR's branch on GitHub.

    Args:
        act: the verb's world.
        target: the PR.
        options: none.

    Returns:
        What was done.
    """
    actcore.gate(act, "update-branch", target.repo)
    act.controls.disarm(act, target, "the branch is updated")
    act.hub.write(
        actcore.Change(kind="update-branch", repo=target.repo, number=target.number)
    )
    return f"update-branch {target.repo}#{target.number}"


def rerun(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Re-run a run's failed jobs, only for a cause of kind runner.

    Args:
        act: the verb's world.
        target: the repository.
        options: ``run``, ``cause`` (``runner``) and ``evidence`` (the annotation).

    Returns:
        What was done.

    Raises:
        actcore.Refused: the cause is not the runner; a red of the code is fixed by
            a push.
    """
    actcore.gate(act, "rerun", target.repo)
    run = actcore.option(options, "run")
    if options.get("cause") != "runner" or not options.get("evidence"):
        raise actcore.Refused(
            "a re-run needs a cause of kind runner with its evidence (the job's"
            " annotation)"
        )
    act.hub.write(actcore.Change(kind="rerun", repo=target.repo, fields={"run": run}))
    return f"rerun {target.repo} run {run}"


def cancel(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Cancel a run that a newer run of its workflow superseded.

    Args:
        act: the verb's world.
        target: the repository.
        options: ``run`` and ``superseded-by``.

    Returns:
        What was done.
    """
    actcore.gate(act, "cancel", target.repo)
    run, newer = actcore.option(options, "run"), actcore.option(
        options, "superseded-by"
    )
    act.hub.write(
        actcore.Change(
            kind="cancel", repo=target.repo, fields={"run": run, "newer": newer}
        )
    )
    return f"cancel {target.repo} run {run} (superseded by {newer})"


def dispatch_workflow(
    act: actcore.Act, target: actcore.Target, options: actcore.Options
) -> str:
    """Dispatch relock.yml or check.yml.

    Args:
        act: the verb's world.
        target: the repository.
        options: ``workflow`` and ``ref``.

    Returns:
        What was done.

    Raises:
        actcore.Refused: another workflow.
    """
    actcore.gate(act, "dispatch-workflow", target.repo)
    workflow, ref = actcore.option(options, "workflow"), actcore.option(options, "ref")
    if workflow not in WORKFLOWS:
        raise actcore.Refused(
            f"{workflow} is not one pitboss dispatches ({', '.join(WORKFLOWS)})"
        )
    act.hub.write(
        actcore.Change(
            kind="dispatch", repo=target.repo, fields={"workflow": workflow, "ref": ref}
        )
    )
    return f"dispatch-workflow {workflow} on {target.repo} at {ref}"


def close(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Close an issue or a PR with GitHub's state_reason.

    Args:
        act: the verb's world.
        target: the issue or PR.
        options: ``reason`` (completed, not_planned, duplicate).

    Returns:
        What was done.

    Raises:
        actcore.Refused: another reason.
    """
    actcore.gate(act, "close", target.repo)
    reason = text(options.get("reason"))
    if reason not in CLOSE_REASONS:
        known = ", ".join(CLOSE_REASONS)
        raise actcore.Refused(f"close names GitHub's state_reason: {known}")
    fields = {"reason": reason}
    change = actcore.Change(
        kind="close-issue", repo=target.repo, number=target.number, fields=fields
    )
    act.hub.write(change)
    return f"close {target.repo}#{target.number} ({reason})"
