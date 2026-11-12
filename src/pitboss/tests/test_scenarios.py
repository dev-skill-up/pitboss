"""Scenarios: the step the rules require at the marked events of real PRs (pitboss#444).

Each timeline in ``scenarios`` was captured by ``pitboss capture-timeline`` from
GitHub. A mark names a moment of it and the step the owner's rules give there;
the test prints what the flow gives at each mark (keyword: scenario) and requires
it. The marks of pitboss 465, 470, 460, 463 and 468 fail on main 482a642: the
flow there gives the step the rules say is wrong.
"""

import json
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_inanyorder, equal_to

from .. import capture, ghapi, steps
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
# A2: a posted ruling's steps are executed at once (a Plan edited since its
# approval does not hold them, A1), A3: a fix round is followed by a review.
MARKS: Mapping[str, Sequence[Mark]] = {
    "dev-skill-up-pitboss-465": [
        Mark("2026-11-11T11:01:51Z", "A2", RULING_STEPS),
        Mark("2026-11-11T11:12:58Z", "A1", "PLAN_EDITED"),
        Mark("2026-11-11T14:21:49Z", "A1", RULING_STEPS),
        Mark("2026-11-11T22:33:56Z", "A1", RULING_STEPS),
        Mark("2026-11-11T22:33:57Z", "A4", "WAIT_FOR_OWNER"),
    ],
    "dev-skill-up-pitboss-470": [
        Mark("2026-11-11T10:57:52Z", "A2", RULING_STEPS),
        Mark("2026-11-11T11:22:14Z", "A1", "PLAN_EDITED"),
        Mark("2026-11-11T14:21:50Z", "A1", RULING_STEPS),
        Mark("2026-11-11T22:33:58Z", "A1", RULING_STEPS),
        Mark("2026-11-11T22:33:59Z", "A4", "WAIT_FOR_OWNER"),
    ],
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


class TestScenarios(unittest.TestCase):
    """The scenarios of the captured PRs."""

    def test_a1_a2_a3_pitboss_465(self) -> None:
        """465: `revise the plan` then `do these steps` is executed (A1, A2)."""
        required("dev-skill-up-pitboss-465")

    def test_a1_a2_a3_pitboss_470(self) -> None:
        """470: the same shape as 465 (A1, A2)."""
        required("dev-skill-up-pitboss-470")

    def test_a3_pitboss_460(self) -> None:
        """460: a Plan check after the ruling's steps is followed by the review (A3)."""
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
        """quire 1083: a refused Plan check is sent back; the ruling's steps (A1, A2)."""
        required("bats-lang-quire-1083")

    def test_a3_bats_650(self) -> None:
        """bats 650: the ruling, the fix round, the review, the merge (A2, A3, A5)."""
        required("bats-lang-bats-650")


def github_bodies() -> Mapping[str, object]:
    """The canned API for a PR 7 with one commit, comment, review and event.

    Returns:
        The bodies, by path.
    """
    sha = "a" * 40
    prefix = "repos/o/r"
    pull = fakes.pull_body(7, head={"sha": sha, "ref": "w7"}, body="B")
    pull["labels"] = [{"name": "p0"}]
    comment = {
        "id": 1,
        "body": "hi",
        "author_association": "MEMBER",
        "created_at": "2026-11-11T00:00:01Z",
        "html_url": "https://example.org/c/1",
        "user": {"login": "someone"},
    }
    return {
        f"{prefix}/pulls/7": pull,
        fakes.page(f"{prefix}/pulls/7/commits"): [
            {"sha": sha, "commit": {"committer": {"date": "2026-11-11T00:00:00Z"}}}
        ],
        fakes.page(f"{prefix}/issues/7/events"): [
            {"event": "labeled", "created_at": "t1", "label": {"name": "p0"}},
            {"event": "assigned", "created_at": "t2"},
        ],
        fakes.page(f"{prefix}/issues/7/comments"): [comment],
        fakes.page(f"{prefix}/pulls/7/reviews"): [],
        fakes.page(f"{prefix}/commits/{sha}/check-runs"): {
            "check_runs": [{"id": 3, "name": "build", "status": "completed"}]
        },
    }


class TestCaptureTimeline(unittest.TestCase):
    """The capture of a timeline."""

    def test_capture_timeline_keeps_what_the_flow_reads(self) -> None:
        """The label events, the comment, the commit and its check runs are kept."""
        github = fakes.github(dict(github_bodies()))
        got = capture.capture(github, "o/r", 7)
        assert_that(got["pull"]["head"]["sha"], equal_to("a" * 40))
        assert_that([each["event"] for each in got["events"]], equal_to(["labeled"]))
        assert_that(got["comments"][0]["html_url"], equal_to("https://example.org/c/1"))
        assert_that(got["comments"][0].get("user"), equal_to(None))
        assert_that(got["checks"]["a" * 40][0]["name"], equal_to("build"))

    def test_capture_timeline_is_json(self) -> None:
        """What it gives is written and read back as it is."""
        github = fakes.github(dict(github_bodies()))
        got = capture.capture(github, "o/r", 7)
        assert_that(json.loads(json.dumps(got)), equal_to(got))

    def test_capture_timeline_only_reads(self) -> None:
        """It asks GitHub for nothing but GETs."""
        github = fakes.github(dict(github_bodies()))
        capture.capture(github, "o/r", 7)
        asked = [" ".join(each) for each in fakes.calls_of(github)]
        assert_that(all("-X" not in each for each in asked), equal_to(True))

    def test_capture_timeline_the_files_are_the_eight_prs(self) -> None:
        """tests/scenarios holds the captured timelines the ticket names."""
        files = sorted(each.stem for each in scenario.DIRECTORY.glob("*.json"))
        assert_that(files, contains_inanyorder(*NAMES))
        for name in NAMES:
            data = scenario.load(name)
            assert_that(f"{data['slug'].replace('/', '-')}-{data['number']}", equal_to(name))
            assert_that(len(data["comments"]) > 0, equal_to(True))

    def test_capture_timeline_replays_the_head_of_each_time(self) -> None:
        """The head at a time is the newest commit made by then."""
        data = scenario.load("dev-skill-up-pitboss-465")
        assert_that(
            scenario.head_at(data, "2026-11-11T11:06:13Z")[:8], equal_to("bc81a081")
        )
        assert_that(
            scenario.head_at(data, "2026-11-11T08:00:00Z")[:8], equal_to("07f55c3b")
        )
        assert_that(
            sorted(scenario.labels_at(data, "2026-11-11T22:40:00Z")),
            equal_to(["paused-owner"]),
        )
        assert_that(sorted(scenario.labels_at(data, "2026-11-11T23:00:00Z")), equal_to([]))
        assert_that(steps.PAUSED_LABEL, equal_to("paused-owner"))
        assert_that(ghapi.PAGE_SIZE, equal_to(100))
