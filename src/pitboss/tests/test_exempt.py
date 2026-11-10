"""Pitboss is not subject to holds, and its PRs are not drafts (pitboss#113)."""

import re
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, starts_with

from .. import brief, briefconfig, briefrepo, configfile, exempt
from . import fakes, quietworld, world
from .briefmake import has_all, has_none, text
from .test_flow_sweep import APPROVED, graded, world_with
from .test_quiet import at, clear_world, lines, pushes, record_path, waiting_world
from .test_slot_commands import next_output

PITBOSS_URL = "https://github.com/dev-skill-up/pitboss.git"
OTHER_URL = "git@github.com:other/repo.git"
QUIRE = "owner/project#3"
PITBOSS_PR = "dev-skill-up/pitboss#3"
LISTED = "other/repo"
READY = "Ready: this project's PRs are not drafts"
DRAFT = "Draft: open the PR as a draft"
SAYING = "pitboss is exempt from holds"
PITBOSS_NEW = "dev-skill-up/pitboss#9"


def remote_to(here: world.World, name: str, url: str) -> None:
    """Add a remote that names a repository and pushes to the world's origin.

    Args:
        here: the world.
        name: the remote's name.
        url: the URL it names.
    """
    fakes.run_git(here.clone, "branch", "-f", "branch-1")
    fakes.run_git(here.clone, "remote", "add", name, url)
    target = str(world.origin_of(here.clone))
    fakes.run_git(here.clone, "config", f"remote.{name}.pushurl", target)


def push(here: world.World, *more: str) -> world.Result:
    """Push at minute 1 of a world.

    Args:
        here: the world.
        *more: the options and git's arguments.

    Returns:
        What the push did.
    """
    return world.again(here, "push", "--now", at(1), "--no-dry-run", *more)


class TestNames(unittest.TestCase):
    """The repository a remote names, and the lists."""

    def test_the_forms_of_a_github_remote(self) -> None:
        """https, ssh and a proxy path name the repository; a path names none."""
        proxy = "http://local_proxy@127.0.0.1:1234/git/dev-skill-up/pitboss"
        urls = (PITBOSS_URL, OTHER_URL, proxy, "/tmp/origin", "origin\n", "")
        found = [exempt.slug_of(url) for url in urls]
        pitboss = "dev-skill-up/pitboss"
        assert_that(found, equal_to([pitboss, LISTED, pitboss, None, None, None]))

    def test_the_listed_and_the_built_in(self) -> None:
        """Pitboss is exempt with an empty list; another repository only if listed."""
        listed = exempt.slugs(["repo", "x/y"], "other")
        found = [
            exempt.is_exempt(exempt.PITBOSS, frozenset()),
            exempt.is_exempt(LISTED, listed),
            exempt.is_exempt("owner/project", listed),
            exempt.is_exempt(None, listed),
            exempt.others(listed),
            exempt.owner_of({"project": {"owner": "o"}}),
            exempt.owner_of({"project": 1}),
            exempt.owner_of({}),
        ]
        expected = [True, True, False, False, [LISTED, "x/y"], "o", "", ""]
        assert_that(found, equal_to(expected))

    def test_the_brief_table_reads_the_list(self) -> None:
        """A bare name belongs to the owner, pitboss is always there, a string fails."""
        document = {"project": {"owner": "o"}, "slots": {"brief": {"no_drafts": ["r"]}}}
        given = briefconfig.from_document(document).no_drafts
        assert_that(sorted(exempt.slugs(given, "o")), equal_to([exempt.PITBOSS, "o/r"]))
        assert_that(briefconfig.from_document({}).no_drafts, equal_to(frozenset()))
        with self.assertRaises(ValueError):
            briefconfig.from_document({"slots": {"brief": {"no_drafts": "r"}}})


class TestPush(unittest.TestCase):
    """``pitboss push`` under pressure."""

    def test_a_pitboss_push_goes_out_while_another_is_held(self) -> None:
        """Both pushes see the same pressure: pitboss goes out, the other is held."""
        here = waiting_world(1)
        remote_to(here, "pitboss", PITBOSS_URL)
        remote_to(here, "elsewhere", OTHER_URL)
        held = push(here, "elsewhere", "branch-1")
        recorded = (pushes(here), lines(here))
        free = push(here, "pitboss", "branch-1")
        found = [
            (held.code, "RUNNER PRESSURE" in held.out, recorded[0]),
            (free.code, free.out.count(SAYING), pushes(here), lines(here)),
        ]
        expected = [(1, True, 0), (0, 1, 1, recorded[1])]
        assert_that(found, equal_to(expected))
        assert_that(free.out, equal_to(f"{exempt.SAYING}\npushed\n"))

    def test_a_listed_repository_is_exempt_too(self) -> None:
        """``[runners] exempt`` adds a repository to pitboss."""
        here = waiting_world(1)
        remote_to(here, "elsewhere", OTHER_URL)
        quietworld.edit_config(here, "[runners]", f'[runners]\nexempt = ["{LISTED}"]')
        free = push(here, "elsewhere", "branch-1")
        assert_that((free.code, pushes(here)), equal_to((0, 1)))
        assert_that(free.out, contains_string(exempt.SAYING))

    def test_a_remote_that_names_no_repository_is_held(self) -> None:
        """A local origin, and a remote git does not know, are held as before."""
        here = waiting_world(1)
        found = [push(here, "origin", "branch-1"), push(here, "nowhere", "branch-1")]
        assert_that([each.code for each in found], equal_to([1, 1]))
        assert_that(pushes(here), equal_to(0))

    def test_no_arguments_use_origin(self) -> None:
        """With no git arguments the remote is origin, which names pitboss here."""
        here = waiting_world(1)
        fakes.run_git(here.clone, "remote", "set-url", "origin", PITBOSS_URL)
        target = str(world.origin_of(here.clone))
        fakes.run_git(here.clone, "config", "remote.origin.pushurl", target)
        found = push(here)
        assert_that((found.code, pushes(here)), equal_to((0, 1)))

    def test_pitboss_has_no_drafts(self) -> None:
        """``--draft`` is refused for pitboss and goes out for the others."""
        here = clear_world()
        remote_to(here, "pitboss", PITBOSS_URL)
        remote_to(here, "elsewhere", OTHER_URL)
        refused = push(here, "--draft", "pitboss", "branch-1")
        shown = (refused.code, pushes(here))
        allowed = push(here, "--draft", "elsewhere", "branch-1")
        assert_that((shown, allowed.code), equal_to(((1, 0), 0)))
        assert_that(refused.out, starts_with("push refused: --draft"))


def with_pitboss(here: world.World) -> world.World:
    """Add a pitboss repository to a world, with the PRs and tickets of the project.

    Args:
        here: the world, whose project has the PRs.

    Returns:
        The same world.
    """
    quietworld.edit_config(
        here, 'repositories = ["lib"]', 'repositories = ["lib", "dev-skill-up/pitboss"]'
    )
    old, new = "repos/owner/project", "repos/dev-skill-up/pitboss"
    for key, body in list(here.bodies.items()):
        if old in key:
            here.bodies[key.replace(old, new)] = body
    return here


def of(output: str, kind: str, reference: str) -> Sequence[str]:
    """The lines of a kind that name a reference.

    Args:
        output: what a command printed.
        kind: the line's first word.
        reference: the PR.

    Returns:
        The lines.
    """
    return re.findall(rf"(?m)^{kind}\b.*{re.escape(reference)}\b.*$", output)


def drafted_pair() -> world.World:
    """A world with a draft of an approved Plan in each of two repositories.

    Returns:
        The world; a job waits for a runner, so the project's draft is held.
    """
    return with_pitboss(world_with([graded(APPROVED, None, 1)], draft=True))


def held_pair() -> world.World:
    """A world as ``drafted_pair`` is, but pitboss's PR is open and ready.

    Returns:
        The world; a job waits for a runner, so the project's draft is held.
    """
    here = drafted_pair()
    key = "repos/dev-skill-up/pitboss/pulls/3"
    body = here.bodies[key]
    assert isinstance(body, dict)
    here.bodies[key] = {**body, "draft": False}
    return here


def swept(here: world.World) -> str:
    """What a sweep of a world printed.

    Args:
        here: the world.

    Returns:
        Its output.
    """
    return world.invoke(here, "sweep", here.config, "--now", world.FUTURE).out


class TestSweep(unittest.TestCase):
    """Two drafts with an approved Plan, one in quire's repository, under pressure."""

    def test_the_next_list_holds_the_undraft_of_the_other_repository_only(self) -> None:
        """The pitboss PR is not held or undrafted; the other waits for the end."""
        shown = next_output(held_pair())
        other, pitboss = of(shown, "NEXT", QUIRE), of(shown, "NEXT", PITBOSS_PR)
        assert_that("HOLD on undrafts" in other[0], equal_to(True))
        assert_that(len(pitboss), equal_to(1))
        assert_that("HOLD" in pitboss[0], equal_to(False))
        assert_that("mark the PR ready" in pitboss[0], equal_to(False))

    def test_a_pitboss_draft_is_marked_ready_without_a_hold(self) -> None:
        """A draft that is there all the same is marked ready, never held."""
        shown = next_output(drafted_pair())
        pitboss = of(shown, "NEXT", PITBOSS_PR)
        assert_that(len(pitboss), equal_to(1))
        assert_that(pitboss[0], contains_string("mark the PR ready"))
        assert_that("HOLD" in pitboss[0], equal_to(False))
        state = of(shown, "PR STATE", PITBOSS_PR)
        assert_that(state[0], contains_string("draft (open ready"))

    def test_the_sweep_says_so_once(self) -> None:
        """The pressure line holds, pitboss is told apart, and no PR line waits."""
        here = held_pair()
        out = swept(here)
        task = [each for each in of(out, "TASK LIST", PITBOSS_PR) if " next " in each]
        state = of(next_output(here), "PR STATE", PITBOSS_PR)
        words = ("HOLD", "WAIT_FOR_UNDRAFT", "UNDRAFT", "mark the PR ready", "pressure")
        found = (
            "RUNNER PRESSURE" in out,
            out.count(SAYING),
            [len(task), len(state)],
            [word for word in words if word in task[0] + state[0]],
            of(out, "HOLD", "new"),
        )
        assert_that(found, equal_to((True, 1, [1, 1], [], [])))

    def test_the_other_repository_still_waits(self) -> None:
        """Its PR STATE line is the wait for an undraft, with no word of drafts."""
        state = of(next_output(held_pair()), "PR STATE", QUIRE)
        assert_that(len(state), equal_to(1))
        assert_that(state[0], starts_with(f"PR STATE {QUIRE}: draft next step: "))
        assert_that(state[0], contains_string("runner pressure"))
        assert_that("open ready" in state[0], equal_to(False))

    def test_no_pressure_no_saying(self) -> None:
        """A sweep that shows no hold does not mention the exemption."""
        here = held_pair()
        for key in [each for each in here.bodies if "/runs/1" in each]:
            here.bodies[key] = {"jobs": []}
        record_path(here).write_text("2029-12-31T23:00:00+00:00 none\n")
        out = swept(here)
        assert_that(
            (SAYING in out, "NO RUNNER PRESSURE" in out), equal_to((False, True))
        )

    def test_next_prints_the_override_rule(self) -> None:
        """The orchestrator is told to override a step a ticketed bug makes wrong."""
        shown = next_output(held_pair())
        rule = exempt.OVERRIDE
        found = (rule in shown.splitlines(), shown.count("OVERRIDE:"))
        assert_that(found, equal_to((True, 1)))
        assert_that(rule, contains_string("cite the ticket"))
        assert_that(rule, contains_string("one pass over the whole PR"))


def for_repository(
    here: world.World, given: briefconfig.Brief, slug: str
) -> briefconfig.Brief:
    """The ``[slots.brief]`` of a world as it holds for a repository.

    Args:
        here: the world.
        given: its ``[slots.brief]``.
        slug: the repository.

    Returns:
        The table for that repository.
    """
    settings = configfile.load(here.config, here.workspace)
    return briefrepo.of_repository(
        given, slug, settings.project.no_drafts, settings.runners.exempt
    )


class TestNoDrafts(unittest.TestCase):
    """The brief and the lines of a repository whose PRs are not drafts."""

    def test_the_brief_of_a_listed_and_an_unlisted_repository(self) -> None:
        """READY for the listed one, DRAFT for the other, from one configuration."""
        here = held_pair()
        quietworld.edit_config(
            here, "[runners]", '[slots.brief]\nno_drafts = ["other/repo"]\n\n[runners]'
        )
        given = configfile.load_brief(here.config, here.workspace)
        briefs = [
            text(brief.Kind.NEW_PR, project=for_repository(here, given, each))
            for each in (LISTED, exempt.PITBOSS, "owner/project")
        ]
        has_all(briefs[0], [READY, "(without `--draft`: this project's PRs are not"])
        has_all(briefs[1], [READY, "Push: push the branch with `git push`"])
        has_none(briefs[0] + briefs[1], [DRAFT, "(add `--draft`"])
        has_all(briefs[2], [DRAFT, "(add `--draft` for a draft PR)"])
        has_none(briefs[2], [READY])

    def test_the_first_step_of_a_pitboss_ticket_is_to_open_ready(self) -> None:
        """``next`` on a ticket of pitboss says ready, on one of the project draft."""
        here = with_pitboss(world.make_world())
        steps = [
            world.again(here, "next", f"{repository}#99").out.strip()
            for repository in ("dev-skill-up/pitboss", "owner/project")
        ]
        assert_that(steps[0], contains_string("open the PR ready for review"))
        assert_that(steps[1], contains_string("open the PR as a draft"))

    def test_the_next_line_of_a_ticket_says_open_ready(self) -> None:
        """A ticket of pitboss is started ready; one of the project is not told so."""
        shown = next_output(held_pair())
        ready = []
        for each in shown.splitlines():
            if "(start a PR" in each:
                ready.append((each.split()[2], exempt.OPEN_READY in each))
        expected = [(PITBOSS_NEW, True), ("owner/project#9", False)]
        assert_that(sorted(ready), equal_to(expected))
