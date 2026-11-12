"""The ``act`` command and the GitHub it writes through (keyword: act-verbs, pitboss#444)."""

import json
import subprocess
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, has_item

from .. import act_commands, actcore, acthub, actinputs, actwiring, ghapi
from . import fakes, world
from .knownkit import BASE, REPO, NUMBER, kit, made

PULL = "owner/project#3"


def _here() -> world.World:
    here = world.make_world()
    here.bodies["user"] = {"login": "pitboss-bot"}
    here.bodies["POST repos/owner/project/issues/3/labels"] = []
    here.bodies["POST repos/owner/project/issues/3/comments"] = {"html_url": "u"}
    here.bodies["name=project"] = {
        "data": {
            "repository": {
                "pullRequests": {"nodes": [{"additions": 3, "deletions": 1}]}
            }
        }
    }
    return here


def _act(here: world.World, *words: str) -> world.Result:
    return world.invoke(
        here, "act", *words, "--config", here.config, "--now", world.FUTURE
    )


class TestCommand(unittest.TestCase):
    """The command line."""

    def test_c17_a_label_is_made_and_recorded(self) -> None:
        """A dry run prints the write; a live one writes it, records it and keeps the owner file."""
        here = _here()
        assert_that(
            _act(here, "label", PULL, "name=p1").out, equal_to(f"label p1 on {PULL}\n")
        )
        done = _act(here, "label", PULL, "name=p1", "--no-dry-run")
        assert_that(done.code, equal_to(0))
        assert_that(
            here.calls,
            has_item(
                [
                    "gh",
                    "api",
                    "-X",
                    "POST",
                    "-f",
                    "labels[]=p1",
                    "repos/owner/project/issues/3/labels",
                ]
            ),
        )
        events = "".join(each.read_text() for each in here.workspace.rglob("*.events"))
        assert_that(events, contains_string("label owner/project#3"))
        assert_that((here.ledger.parent / actwiring.OWNER).exists(), equal_to(True))
        assert_that(
            _act(here, "comment", PULL, "body=hi", "--no-dry-run").code, equal_to(0)
        )
        again = "".join(each.read_text() for each in here.workspace.rglob("*.events"))
        assert_that(again, equal_to(events))

    def test_c17_refusals_exit_2(self) -> None:
        """No verb, a word that is no option, and a STOP each exit 2 and write nothing."""
        here = _here()
        for words, said in (
            (("nope", PULL), "no verb"),
            (("label", PULL, "name"), "is not an option"),
            (("merge", PULL), "act merge: refused"),
        ):
            done = _act(here, *words)
            assert_that((done.code, said in done.err), equal_to((2, True)))
        assert_that([call for call in here.calls if "-X" in call], equal_to([]))

    def test_c17_targets(self) -> None:
        """A PR, a repository and all."""
        assert_that(
            act_commands.target_of("o/r#4"),
            equal_to(actcore.Target(repo="o/r", number=4)),
        )
        assert_that(act_commands.target_of("all"), equal_to(actcore.Target(repo="all")))

    def test_c17_the_ledger_event_names_the_branch(self) -> None:
        """A checked write is recorded with the PR's branch and head; another is not."""
        given = kit()
        hub = made(given)
        target = actcore.Target(repo=REPO, number=NUMBER)
        event = act_commands.ledger_event(
            hub.act, "merge", target, {}, "2026-11-12T00:00:00"
        )
        branch = str(dict(BASE.pull["head"])["ref"])  # type: ignore[call-overload]
        assert_that(
            event.what if event else "",
            equal_to(f"merge {REPO}#{NUMBER} {branch} at act"),
        )
        assert_that(
            act_commands.ledger_event(hub.act, "comment", target, {}, ""),
            equal_to(None),
        )
        pushed = act_commands.ledger_event(
            hub.act, "push", actcore.Target(repo=REPO), {"branch": "w"}, ""
        )
        assert_that(pushed.what if pushed else "", equal_to(f"push {REPO}#0 w at act"))


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
        fields = {
            "body": "b",
            "title": "t",
            "labels": "a,b",
            "id": "9",
            "reason": "completed",
            "head": "h",
            "base": "main",
        }
        fields |= {
            "name": "p 1",
            "node_id": "N",
            "run": "5",
            "workflow": "check.yml",
            "ref": "main",
            "branch": "w/1",
        }
        for kind, words in acthub.WRITES.items():
            said = list(
                words(actcore.Change(kind=kind, repo="o/r", number=3, fields=fields))
            )
            assert_that(said[0], equal_to("gh"))
        issue = acthub.WRITES["issue"](
            actcore.Change(kind="issue", repo="o/r", fields=fields)
        )
        empty = acthub.WRITES["comment"](
            actcore.Change(kind="comment", repo="o/r", number=3, fields={"body": ""})
        )
        assert_that("-f" in empty, equal_to(False))
        assert_that(
            list(issue),
            equal_to(
                [
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
            ),
        )

    def test_c17_reads_and_writes(self) -> None:
        """A PR, a listing a line each, a write's answer, and a PR given its base."""
        answers = {
            "repos/o/r/pulls/3": json.dumps({"number": 3}),
            "repos/o/r/pulls?state=open&per_page=100": '{"number": 1}\n{"number": 2}\n',
            "repos/o/r/issues/3/timeline?per_page=100": "[]\n",
            "repos/o/r/issues?state=open&per_page=100&labels=pitboss-hold": "",
            "repos/o/r": json.dumps({"default_branch": "trunk"}),
            "repos/o/r/pulls": "7\n",
        }
        calls, github = _github(answers)
        hub = acthub.GhHub(github=github)
        assert_that(hub.pull("o/r", 3), equal_to({"number": 3}))
        assert_that([each["number"] for each in hub.pulls("o/r")], equal_to([1, 2]))
        assert_that(
            (hub.timeline("o/r", 3), hub.issues("o/r", "pitboss-hold")),
            equal_to(([], [])),
        )
        assert_that(
            hub.write(
                actcore.Change(
                    kind="pr",
                    repo="o/r",
                    fields={"head": "h", "title": "t", "body": "b"},
                )
            ),
            equal_to("7"),
        )
        assert_that(calls[-1], has_item("base=trunk"))
        answers["repos/o/r/pulls/4"] = "[]"
        assert_that(hub.pull("o/r", 4), equal_to({}))


class TestInputs(unittest.TestCase):
    """The verdict's inputs, read live."""

    def test_c17_every_required_input_is_read(self) -> None:
        """Rules, runs, statuses, tickets, files, blockers and the timeline; a failed read is kept."""
        answers = {
            "repos/o/r/rules/branches/main": json.dumps(
                [
                    {
                        "type": "required_status_checks",
                        "parameters": {
                            "required_status_checks": [{"context": "check"}]
                        },
                    },
                    {"type": "merge_queue"},
                ]
            ),
            "repos/o/r": json.dumps({"default_branch": "main"}),
            "repos/o/r/commits/h/check-runs?per_page=100": json.dumps(
                {"check_runs": [{"name": "check"}]}
            ),
            "repos/o/r/issues/1": json.dumps({"state": "open"}),
            "repos/x/y/issues/4": json.dumps({"state": "closed"}),
            "repos/o/r/pulls/3/files?per_page=100": json.dumps([{"filename": "a"}]),
            "repos/o/r/issues/3/timeline?per_page=100": "",
        }
        _, github = _github(answers)
        settings = actinputs.Settings(
            identity="bot", authors=["dependabot[bot]"], max_lines={"o/r": 400}
        )
        made_ = actinputs.inputs(actinputs.reader(github), settings)
        pull = {
            "body": "Fixes #1\n\nBlocked by x/y#4 and #9\n",
            "base": {"ref": "main"},
            "head": {"sha": "h"},
        }
        ctx = made_("o/r", 3, pull, [])
        assert_that(
            (ctx["required_checks"], ctx["merge_queue"], ctx["max_lines"]),
            equal_to((["check"], True, 400)),
        )
        assert_that(
            (ctx["check_runs"], ctx["files"], ctx["timeline"]),
            equal_to(([{"name": "check"}], [{"filename": "a"}], [])),
        )
        assert_that(ctx["blockers"], equal_to({"x/y#4": "closed", "#9": "not read"}))
        assert_that(list(dict(ctx["tickets"]).keys()), equal_to(["o/r#1"]))  # type: ignore[call-overload]
        assert_that("_error" in dict(ctx["statuses"]), equal_to(True))  # type: ignore[call-overload]
        assert_that(ctx["authors"], equal_to({"bot", "dependabot[bot]"}))


class TestWiring(unittest.TestCase):
    """The owner file, the order of work's inputs and the pre-push check."""

    def test_c17_the_owner_file_round_trips(self) -> None:
        """A missing file is no message; what is written is read back."""
        path = fakes.directory() / actwiring.OWNER
        assert_that(actwiring.owner_of(path), equal_to(actcore.Owner()))
        actwiring.write_owner(
            path, actcore.Owner(messages=["m1"], dispositions={"m1": "cap"}, cap=2)
        )
        assert_that(
            actwiring.owner_of(path),
            equal_to(actcore.Owner(messages=["m1"], dispositions={"m1": "cap"}, cap=2)),
        )

    def test_c17_the_pre_push_check_says_its_status_and_output(self) -> None:
        """Both streams are kept."""

        def run(words: Sequence[str]) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(list(words), 1, "out\n", "err\n")

        assert_that(actwiring.prepush(run)(), equal_to((1, "out\nerr\n")))

    def test_c17_the_p90_is_read_once_and_an_unread_one_is_0(self) -> None:
        """Nine of ten sizes are at or under the percentile."""
        nodes = [{"additions": size, "deletions": 0} for size in range(1, 11)]
        calls, github = _github(
            {
                "name=r": json.dumps(
                    {"data": {"repository": {"pullRequests": {"nodes": nodes}}}}
                )
            }
        )
        found = actwiring.P90(github=github)
        assert_that(
            (
                found["o/r"],
                found.get("o/r"),
                found.get("o/none"),
                len(found),
                sorted(found),
            ),
            equal_to((9, 9, 0, 2, ["o/none", "o/r"])),
        )
        assert_that(len(calls), equal_to(2))

    def test_c17_the_order_of_work_reads_slots_prs_and_tickets(self) -> None:
        """The configured slots and ledger, the open PRs and the tickets of each priority."""
        here = _here()
        for repo in ("owner/project", "owner/lib"):
            here.bodies[f"repos/{repo}/pulls?state=open&per_page=100"] = [
                {"number": 5, "created_at": "2026-11-01"}
            ]
            for label in ("p0", "p1", "p2", "p3"):
                issues = [
                    {"number": 6, "created_at": "2026-11-02"},
                    {"number": 5, "pull_request": {}},
                ]
                here.bodies[
                    f"repos/{repo}/issues?state=open&per_page=100&labels={label}"
                ] = issues
        done = _act(here, "dispatch-next", "all")
        assert_that(
            (done.code, done.out + done.err), equal_to((0, "owner/project#5\n"))
        )
