"""Scenarios: the step the rules require at the marked events of real PRs.

Each timeline in ``scenarios`` was captured by ``pitboss capture-timeline`` from
GitHub. A mark names a moment of it and the step the owner's rules give there;
the test prints what the flow gives at each mark (keyword: scenario) and requires
it. The marks of pitboss 465, 470, 460, 463 and 468 fail on main 482a642: the
flow there gives the step the rules say is wrong.
"""

import argparse
import contextlib
import io
import json
import pathlib
import tempfile
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_inanyorder, contains_string, equal_to

from .. import capture, capture_commands, expansion, ghapi, plandigest, steps
from . import fakes, scenario
from .scenario import Mark

RULING_STEPS = "WORKER:RULING_STEPS"
REVIEW_STEPS = "REGULAR_REVIEW:RULING_STEPS"
NAMES = (
    "dev-skill-up-pitboss-465",
    "dev-skill-up-pitboss-470",
    "dev-skill-up-pitboss-460",
    "dev-skill-up-pitboss-463",
    "dev-skill-up-pitboss-468",
    "bats-lang-quire-1104",
    "bats-lang-quire-1083",
    "bats-lang-bats-650",
)


def revised_then_ruled(times: Sequence[str]) -> Sequence[Mark]:
    """The marks of a PR whose Plan was revised, then ruled `do these steps`.

    Args:
        times: the five moments, in order.

    Returns:
        The marks (A1, A2, A4).
    """
    rules = ("A2", "A1", "A1", "A1", "A4")
    wants = (RULING_STEPS, "PLAN_EDITED", RULING_STEPS, RULING_STEPS, "IDLE")
    return [Mark(*each) for each in zip(times, rules, wants)]


# A2: a posted ruling's steps are executed at once (a Plan edited since its
# approval does not hold them, A1), A3: a fix round is followed by a review.
MARKS: Mapping[str, Sequence[Mark]] = {
    "dev-skill-up-pitboss-465": revised_then_ruled(
        (
            "2026-11-11T11:01:51Z",
            "2026-11-11T11:12:58Z",
            "2026-11-11T14:21:49Z",
            "2026-11-11T22:33:56Z",
            "2026-11-11T22:33:57Z",
        )
    ),
    "dev-skill-up-pitboss-470": revised_then_ruled(
        (
            "2026-11-11T10:57:52Z",
            "2026-11-11T11:22:14Z",
            "2026-11-11T14:21:50Z",
            "2026-11-11T22:33:58Z",
            "2026-11-11T22:33:59Z",
        )
    ),
    "dev-skill-up-pitboss-460": [
        Mark("2026-11-11T04:26:53Z", "A2", RULING_STEPS),
        Mark("2026-11-11T04:41:11Z", "A3", REVIEW_STEPS),
    ],
    "dev-skill-up-pitboss-463": [
        Mark("2026-11-11T08:15:31Z", "A5", "MERGE"),
        Mark("2026-11-11T08:17:34Z", "A2", RULING_STEPS),
    ],
    "dev-skill-up-pitboss-468": [
        Mark("2026-11-11T09:26:27Z", "A2", RULING_STEPS),
        Mark("2026-11-11T09:36:03Z", "A3", REVIEW_STEPS),
    ],
    "bats-lang-quire-1104": [
        Mark("2026-11-11T17:47:59Z", "I5", "WORKER:FIX_CI"),
    ],
    "bats-lang-quire-1083": [
        Mark("2026-11-10T14:42:15Z", "A1", "SEND_BACK_PLAN_CHECK"),
        Mark("2026-11-11T21:11:40Z", "A2", RULING_STEPS),
    ],
    "bats-lang-bats-650": [
        Mark("2026-11-11T18:50:54Z", "A2", RULING_STEPS),
        Mark("2026-11-11T18:59:13Z", "A3", "REGULAR_REVIEW:EXECUTION_ONLY"),
        Mark("2026-11-11T19:02:28Z", "A5", "MERGE"),
    ],
}


def required(name: str) -> None:
    """Print and require the step at every mark of a timeline.

    Args:
        name: the timeline.
    """
    for mark in MARKS[name]:
        print(scenario.printed(name, mark))
        got = scenario.kind(
            scenario.step_at(scenario.load(name), mark.when, mark.settled)
        )
        assert_that(got, equal_to(mark.want), f"{name} {mark.when} [{mark.rule}]")


def digest_kept(name: str) -> None:
    """Plan-check at the next head leaves the approved Plan's digest as it was.

    The Plan is the one of the captured body. The next head's Actions addresses
    carry other run ids; the digest a review records ignores them (the first of
    ``accepted_digests``), the old one that kept them (the second) is the one the
    captured Plan check comment of that head printed, and it changes.

    Args:
        name: the timeline.
    """
    data = scenario.load(name)
    pull, comments = data["pull"], data["comments"]
    assert isinstance(pull, dict) and isinstance(comments, list)
    plan = plandigest.section(str(pull["body"]))
    later = expansion.RUN_ADDRESS.sub(
        lambda m: f"{m[1]}/actions/runs/9{m[0][-3:]}", plan
    )
    kept, moved = expansion.accepted_digests(plan), expansion.accepted_digests(later)
    bodies = [str(each["body"]) for each in comments]
    printed = [
        each.split("Plan digest: ")[1][:16]
        for each in bodies
        if each.startswith("Plan check") and "Plan check: ok" in each
    ]
    assert_that(
        [kept[0] == moved[0], kept[1] == moved[1], printed[-1] == kept[1]],
        equal_to([True, False, True]),
        f"{name}: the digest of the Plan at the next head",
    )


class TestScenarios(unittest.TestCase):
    """The scenarios of the captured PRs."""

    def test_a1_a2_a3_pitboss_465(self) -> None:
        """465: `revise the plan` then `do these steps` is executed (A1, A2)."""
        required("dev-skill-up-pitboss-465")
        digest_kept("dev-skill-up-pitboss-465")

    def test_a1_a2_a3_pitboss_470(self) -> None:
        """470: the same shape as 465 (A1, A2)."""
        required("dev-skill-up-pitboss-470")
        digest_kept("dev-skill-up-pitboss-470")

    def test_a3_pitboss_460(self) -> None:
        """460: a Plan check after the ruling's steps gets the review (A3)."""
        required("dev-skill-up-pitboss-460")

    def test_a2_pitboss_463(self) -> None:
        """463: a ruling after an approving review voids the merge (A2)."""
        required("dev-skill-up-pitboss-463")

    def test_a3_pitboss_468(self) -> None:
        """468: the review follows the fix round (A3)."""
        required("dev-skill-up-pitboss-468")

    def test_i5_quire_1104(self) -> None:
        """quire 1104: a red CI is fixed, not reviewed (I5)."""
        required("bats-lang-quire-1104")

    def test_a1_quire_1083(self) -> None:
        """quire 1083: a refused Plan check is sent back, then the steps (A1, A2)."""
        required("bats-lang-quire-1083")

    def test_a3_bats_650(self) -> None:
        """bats 650: the ruling, the fix round, the review, the merge (A2-A5)."""
        required("bats-lang-bats-650")


SHA = "a" * 40
PREFIX = "repos/o/r"
URL = "https://example.org/c/1"
COMMENT = {
    "id": 1,
    "body": "hi",
    "author_association": "MEMBER",
    "created_at": "2026-11-11T00:00:01Z",
    "html_url": URL,
    "user": {"login": "someone"},
}
COMMIT = {"sha": SHA, "commit": {"committer": {"date": "2026-11-11T00:00:00Z"}}}
EVENTS = [
    {"event": "labeled", "created_at": "t1", "label": {"name": "p0"}},
    {"event": "assigned", "created_at": "t2"},
]
RUNS = {"check_runs": [{"id": 3, "name": "build", "status": "completed"}]}


def github_bodies() -> Mapping[str, object]:
    """The canned API for a PR 7 with one commit, comment, review and event.

    Returns:
        The bodies, by path.
    """
    pull = fakes.pull_body(7, head={"sha": SHA, "ref": "w7"}, body="B")
    pull["labels"] = [{"name": "p0"}]
    return {
        f"{PREFIX}/pulls/7": pull,
        fakes.page(f"{PREFIX}/pulls/7/commits"): [COMMIT],
        fakes.page(f"{PREFIX}/issues/7/events"): EVENTS,
        fakes.page(f"{PREFIX}/issues/7/comments"): [COMMENT],
        fakes.page(f"{PREFIX}/pulls/7/reviews"): [],
        fakes.page(f"{PREFIX}/commits/{SHA}/check-runs"): RUNS,
    }


EDITS_ANSWER: capture.Item = {
    "data": {
        "repository": {
            "pullRequest": {
                "userContentEdits": {
                    "nodes": [
                        {"createdAt": "T2", "editor": {"login": "w"}, "diff": "second"},
                        {"createdAt": "T1", "editor": None, "diff": None},
                    ]
                }
            }
        }
    }
}
GRAPHQL = f"query={capture.EDITS_QUERY}"


def seven() -> tuple[ghapi.GitHub, str]:
    """The fake API and the JSON the capture of PR 7 gives.

    Returns:
        Both.
    """
    github = fakes.github(dict(github_bodies()))
    got = capture.capture(github, "o/r", 7, capture.body_edits(EDITS_ANSWER))
    return github, json.dumps(got, sort_keys=True)


def arguments(
    to: str | None, edits: str | None = None, graphql: object = EDITS_ANSWER
) -> argparse.Namespace:
    """The command's arguments for PR 7 with the canned API.

    Args:
        to: the file to write, or None to print.
        edits: the file of body edits, or None to ask GraphQL.
        graphql: what GraphQL answers (None: the call is refused).

    Returns:
        The namespace.
    """
    bodies = {**github_bodies(), GRAPHQL: graphql}
    run = fakes.FakeProcesses(bodies=bodies)
    return argparse.Namespace(pull="o/r#7", to=to, edits=edits, safe_run=run)


class TestCaptureTimeline(unittest.TestCase):
    """The capture of a timeline."""

    def test_capture_timeline_keeps_what_the_flow_reads(self) -> None:
        """The label events, the comment, the commit and its check runs are kept."""
        got = seven()[1]
        kept = [f'"sha": "{SHA}"', URL, '"event": "labeled"', "build"]
        for each in kept:
            assert_that(got, contains_string(each))
        left_out = ['"event": "assigned"', "someone"]
        assert_that([each in got for each in left_out], equal_to([False, False]))

    def test_capture_timeline_is_json(self) -> None:
        """What it gives is written and read back as it is."""
        got = seven()[1]
        assert_that(json.dumps(json.loads(got), sort_keys=True), equal_to(got))

    def test_capture_timeline_only_reads(self) -> None:
        """It asks GitHub for nothing but GETs."""
        asked = [" ".join(each) for each in fakes.calls_of(seven()[0])]
        assert_that(all("-X" not in each for each in asked), equal_to(True))

    def test_capture_timeline_the_files_are_the_eight_prs(self) -> None:
        """tests/scenarios holds the captured timelines the ticket names."""
        files = sorted(each.stem for each in scenario.DIRECTORY.glob("*.json"))
        assert_that(files, contains_inanyorder(*NAMES))
        for name in NAMES:
            data = scenario.load(name)
            slug = f"{data['slug'].replace('/', '-')}-{data['number']}"
            assert_that((slug, len(data["comments"]) > 0), equal_to((name, True)))

    def test_capture_timeline_replays_the_head_of_each_time(self) -> None:
        """The head at a time is the newest commit made by then."""
        data = scenario.load("dev-skill-up-pitboss-465")
        heads = [
            scenario.head_at(data, when)[:8]
            for when in ("2026-11-11T11:06:13Z", "2026-11-11T08:00:00Z")
        ]
        assert_that(heads, equal_to(["bc81a081", "07f55c3b"]))
        labels = [
            sorted(scenario.labels_at(data, when))
            for when in ("2026-11-11T22:40:00Z", "2026-11-11T23:00:00Z")
        ]
        assert_that(labels, equal_to([[steps.PAUSED_LABEL], []]))
        assert_that(steps.PAUSED_LABEL, equal_to("paused-owner"))
        assert_that(ghapi.PAGE_SIZE, equal_to(100))

    def test_capture_timeline_command_writes_the_file(self) -> None:
        """`capture-timeline OWNER/NAME#N --to FILE` writes the capture."""
        with tempfile.TemporaryDirectory() as folder:
            target = pathlib.Path(folder) / "t.json"
            capture_commands.capture_timeline(arguments(str(target)))
            written = target.read_text(encoding="utf-8")
        assert_that(json.loads(written)["number"], equal_to(7))

    def test_capture_timeline_command_prints_without_a_file(self) -> None:
        """Without `--to` the capture is printed."""
        with contextlib.redirect_stdout(io.StringIO()) as out:
            capture_commands.capture_timeline(arguments(None))
        assert_that(json.loads(out.getvalue())["number"], equal_to(7))

    def test_capture_timeline_command_refuses_a_bad_pull(self) -> None:
        """An argument that is not OWNER/NAME#N exits with the reason."""
        args = argparse.Namespace(pull="nope", to=None, edits=None, safe_run=None)
        with self.assertRaises(SystemExit) as raised:
            capture_commands.capture_timeline(args)
        assert_that(str(raised.exception), contains_string("not OWNER/NAME#NUMBER"))
