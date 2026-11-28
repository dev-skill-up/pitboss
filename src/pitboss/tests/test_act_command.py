"""The ``act`` command and the GitHub it writes through.

The keyword is act-verbs, pitboss#444.
"""

import json
import subprocess
import sys
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to, has_item

from .. import actcore, acthub, actinputs, actledger, actwiring, ghapi
from ..totaljson import members
from . import fakehub, fakes, forgetting, knownshipped, world
from .knownkit import NUMBER, REPO, base_map, made
from .says import errs, exits, outs
from .fakes import calls_with
from ..actledger import Done

HOLD = actcore.HOLD_LABEL
PULL = "owner/project#3"


LABEL_CALL = [
    "gh",
    "api",
    "-X",
    "POST",
    "-f",
    f"labels[]={actcore.HOLD_LABEL}",
    "repos/owner/project/issues/3/labels",
]
FIELDS = {
    "body": "b",
    "title": "t",
    "labels": "a,b",
    "id": "9",
    "reason": "completed",
    "head": "h",
    "base": "main",
    "name": "p 1",
    "node_id": "N",
    "run": "5",
    "workflow": "check.yml",
    "ref": "main",
    "branch": "w/1",
}
ISSUE_CALL = [
    "gh",
    "api",
    "-X",
    "POST",
    "-f",
    "title=t",
    "-f",
    "body=b",
    "-f",
    "labels[]=a",
    "-f",
    "labels[]=b",
    "--jq",
    ".number",
    "repos/o/r/issues",
]
HUB_ANSWERS = {
    "repos/o/r/pulls/3": json.dumps({"number": 3}),
    "repos/o/r/pulls?state=open&per_page=100&page=1": '[{"number": 1}, {"number": 2}]',
    "repos/o/r/issues/3/timeline?per_page=100&page=1": "[]",
    "repos/o/r/issues?state=open&labels=pitboss-hold&per_page=100&page=1": "[]",
    "repos/o/r": json.dumps({"default_branch": "trunk"}),
    "repos/o/r/pulls": "7\n",
}
RULES = [
    {
        "type": "required_status_checks",
        "parameters": {"required_status_checks": [{"context": "check"}]},
    },
    {"type": "merge_queue"},
]
INPUT_ANSWERS = {
    "repos/o/r/rules/branches/main": json.dumps(RULES),
    "repos/o/r": json.dumps({"default_branch": "main"}),
    "repos/o/r/commits/h/check-runs?per_page=100": json.dumps(
        {"check_runs": [{"name": "check"}]}
    ),
    "repos/o/r/issues/1": json.dumps({"state": "open"}),
    "repos/x/y/issues/4": json.dumps({"state": "closed"}),
    "repos/o/r/pulls/3/files?per_page=100&page=1": json.dumps([{"filename": "a"}]),
    "repos/o/r/issues/3/timeline?per_page=100&page=1": "[]",
}
BLOCKED_PULL = {
    "body": "Fixes #1\n\nBlocked by x/y#4 and #9\n",
    "base": {"ref": "main"},
    "head": {"sha": "h"},
}


def _events(here: world.World) -> str:
    return "".join(each.read_text() for each in here.workspace.rglob("*.events"))


def _recorded(hub: fakehub.Made, done: actledger.Done) -> str:
    event = actledger.ledger_event(hub.act, done, "2026-11-12T00:00:00")
    return event.what if event else ""


OPEN = "/pulls?state=open"


def _listed(number: int) -> Mapping[str, object]:
    # an open PR as the listing gives it: one path reads its branch and age
    return {"number": number, "head": {"ref": f"b{number}"}, "created_at": "2026-11"}


def _here() -> world.World:
    here = world.make_world()
    listings = {world.PROJECT: [_listed(n) for n in (1, 2, 3)], world.LIBRARY: []}
    here.bodies.update(
        {fakes.page(repo + OPEN): found for repo, found in listings.items()}
    )
    here.bodies["user"] = {"login": "pitboss-bot"}
    here.bodies["POST repos/owner/project/issues/3/labels"] = []
    here.bodies["POST repos/owner/project/issues/3/comments"] = {"html_url": "u"}
    return here


def _shown(here: world.World, label: str) -> None:
    pull = here.bodies["repos/owner/project/pulls/3"]
    pull["labels"] = [{"name": label}]  # type: ignore[index]
    here.bodies["repos/owner/project/issues/3"] = {**pull}  # type: ignore[dict-item]


def _act(here: world.World, *words: str) -> world.Result:
    return world.invoke(
        here, "act", *words, "--config", here.config, "--now", world.FUTURE
    )


class TestCommand(unittest.TestCase):
    """The command line."""

    def test_c17_a_label_is_made_and_recorded(self) -> None:
        """A dry run prints the write; a live one writes it.

        Records it and keeps the owner file.
        """
        here = _here()
        _shown(here, HOLD)
        assert_that(
            _act(here, "label", PULL, f"name={HOLD}").out,
            equal_to(f"label {HOLD} on {PULL}\n"),
        )
        done = _act(here, "label", PULL, f"name={HOLD}", "--no-dry-run")
        exits(done, 0)
        assert_that(LABEL_CALL in here.calls, equal_to(True))
        events = _events(here)
        assert_that(events, contains_string("label owner/project#3"))
        assert_that((here.ledger.parent / actwiring.OWNER).exists(), equal_to(True))
        exits(_act(here, "comment", PULL, "body=hi", "--no-dry-run"), 0)
        assert_that(_events(here), equal_to(events))

    def test_c29_a_live_action_whose_pr_did_not_change_is_refused(self) -> None:
        """The fake GitHub applies no label: the write is made, then refused."""
        here = forgetting.forgetful(_here())
        done = _act(here, "label", PULL, f"name={HOLD}", "--no-dry-run")
        errs(done, 2, "NOT LANDED")
        _shown(here, HOLD)
        exits(_act(here, "label", PULL, f"name={HOLD}", "--no-dry-run"), 0)

    def test_a_removed_label_is_shown_gone(self) -> None:
        """A removal is read back too: the label is no longer on the PR."""
        here = _here()
        _shown(here, HOLD)
        here.bodies[f"DELETE repos/owner/project/issues/3/labels/{HOLD}"] = []
        removed = _act(
            here, "label", PULL, f"name={HOLD}", "remove=yes", "--no-dry-run"
        )
        exits(removed, 0)

    def test_c17_a_priority_or_a_paused_owner_label_is_refused(self) -> None:
        """Only the owner changes a priority; paused-owner is not added."""
        here = _here()
        for name in ("p0", "p1", "p2", "p3", "paused-owner"):
            done = _act(here, "label", PULL, f"name={name}", "--no-dry-run")
            errs(done, 2, name)
        assert_that(LABEL_CALL in here.calls, equal_to(False))

    def test_c17_refusals_exit_2(self) -> None:
        """No verb, a word that is no option.

        And a STOP each exit 2 and write nothing.
        """
        here = _here()
        for words, said in (
            (("nope", PULL), "no verb"),
            (("label", PULL, "name"), "is not an option"),
        ):
            done = _act(here, *words)
            errs(done, 2, said)
        edited = _act(here, "comment-edit", PULL, "id=1", "body=x")
        outs(edited, 2, "not a comment pitboss")
        outs(_act(here, "merge", PULL), 2, f"NOT DONE: merge {PULL}")
        assert_that(calls_with(here.calls, "-X"), equal_to([]))

    def test_c17_targets(self) -> None:
        """A PR, a repository and all."""
        assert_that(
            actledger.target_of("o/r#4"),
            equal_to(actcore.Target(repo="o/r", number=4)),
        )
        assert_that(actledger.target_of("all"), equal_to(actcore.Target(repo="all")))

    def test_c17_the_ledger_event_names_the_branch(self) -> None:
        """A checked write is recorded with the PR's branch and head; another is not."""
        hub = made(knownshipped.shipped())
        target = actcore.Target(repo=REPO, number=NUMBER)
        branch = str(base_map("pull", "head")["ref"])
        merged = _recorded(hub, Done(verb="merge", target=target, options={}))
        assert_that(merged, equal_to(f"merge {REPO}#{NUMBER} {branch} at act"))
        comment = Done(verb="comment", target=target, options={})
        assert_that(actledger.ledger_event(hub.act, comment, ""), equal_to(None))
        push = Done(
            verb="push", target=actcore.Target(repo=REPO), options={"branch": "w"}
        )
        assert_that(_recorded(hub, push), equal_to(f"push {REPO}#0 w at act"))


def _github(answers: dict[str, str]) -> tuple[list[Sequence[str]], ghapi.GitHub]:
    calls: list[Sequence[str]] = []

    def run(
        words: Sequence[str], /, **ignored: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(words))
        key = words[-1]
        if key not in answers:
            raise subprocess.CalledProcessError(1, list(words), "", "HTTP 404")
        return subprocess.CompletedProcess(list(words), 0, answers[key], "")

    return calls, ghapi.GitHub(run=run, mutate=run)


class TestHub(unittest.TestCase):
    """Each write is one ``gh`` call; reads follow every page."""

    def test_c17_every_write_kind_has_its_call(self) -> None:
        """The table covers every kind a verb writes, with the path last."""
        firsts = {
            words(actcore.Change(kind=kind, repo="o/r", number=3, fields=FIELDS))[0]
            for kind, words in acthub.WRITES.items()
        }
        assert_that(firsts, equal_to({"gh"}))
        issue = acthub.WRITES["issue"](
            actcore.Change(kind="issue", repo="o/r", fields=FIELDS)
        )
        empty = acthub.WRITES["comment"](
            actcore.Change(kind="comment", repo="o/r", number=3, fields={"body": ""})
        )
        assert_that("-f" in empty, equal_to(False))
        assert_that(list(issue), equal_to(ISSUE_CALL))

    def test_c17_reads_and_writes(self) -> None:
        """A PR, a listing a line each, a write's answer, and a PR given its base."""
        answers = dict(HUB_ANSWERS)
        calls, github = _github(answers)
        hub = acthub.hub_of(github)
        assert_that(hub.pull("o/r", 3), equal_to({"number": 3}))
        assert_that(
            [each["number"] for each in hub.open_pulls("o/r")], equal_to([1, 2])
        )
        assert_that(
            (hub.timeline("o/r", 3), hub.issues("o/r", "pitboss-hold")),
            equal_to(([], [])),
        )
        fields = {"head": "h", "title": "t", "body": "b"}
        made_pr = hub.write(actcore.Change(kind="pr", repo="o/r", fields=fields))
        assert_that(made_pr, equal_to("7"))
        assert_that(calls[-1], has_item("base=trunk"))
        answers["repos/o/r/pulls/4"] = "[]"
        assert_that(hub.pull("o/r", 4), equal_to({}))


class TestInputs(unittest.TestCase):
    """The verdict's inputs, read live."""

    def test_c17_every_required_input_is_read(self) -> None:
        """Rules, runs, statuses, tickets, files and the timeline.

        A failed read is kept.
        """
        _, github = _github(INPUT_ANSWERS)
        settings = actinputs.Settings(identity="bot", authors=["dependabot[bot]"])
        made_ = actinputs.live_inputs(actinputs.reader(github), settings)
        ctx = made_("o/r", 3, dict(BLOCKED_PULL), [])
        assert_that(
            (ctx["required_checks"], ctx["merge_queue"]),
            equal_to((["check"], True)),
        )
        assert_that(
            (ctx["check_runs"], ctx["files"], ctx["timeline"]),
            equal_to(([{"name": "check"}], [{"filename": "a"}], [])),
        )
        assert_that(list(members(ctx["tickets"])), equal_to(["o/r#1"]))
        assert_that("_error" in members(ctx["statuses"]), equal_to(True))
        assert_that(ctx["authors"], equal_to({"bot", "dependabot[bot]"}))


class TestWiring(unittest.TestCase):
    """The owner file, the order of work's inputs and the pre-push check."""

    def test_c17_the_owner_file_round_trips(self) -> None:
        """A missing file is no message; what is written is read back."""
        path = fakes.directory() / actwiring.OWNER
        assert_that(actwiring.owner_of(path), equal_to(actcore.Owner()))
        actwiring.write_owner(
            path,
            actcore.Owner(messages=("m1",), dispositions={"m1": "cap"}, caps={"m1": 2}),
        )
        assert_that(
            actwiring.owner_of(path),
            equal_to(
                actcore.Owner(
                    messages=("m1",), dispositions={"m1": "cap"}, caps={"": 2}
                )
            ),
        )

    def test_c17_the_pre_push_check_says_its_status_and_output(self) -> None:
        """Both streams are kept."""

        def run(words: Sequence[str]) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(list(words), 1, "out\n", "err\n")

        assert_that(actwiring.prepush(run)(), equal_to((1, "out\nerr\n")))

    def test_c17_a_quiet_run_keeps_the_output_of_a_failed_command(self) -> None:
        """A failing command does not raise."""
        code = "import sys; print('said'); sys.exit(3)"
        done = actwiring.quiet([sys.executable, "-c", code])
        assert_that((done.returncode, done.stdout), equal_to((3, "said\n")))
