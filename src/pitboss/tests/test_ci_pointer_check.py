"""Tests for the check of a Plan's CI pointers (keyword: ci-pointer, pitboss#335)."""

import unittest
import dataclasses
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import cipointer, cipointercheck, plancheckconfig
from . import diffrepo, world
from .linting import write_text
from .repositories import IDENTITY, run_git
from .test_expand_commands import real_world

WORKFLOW = """\
name: check
jobs:
  build:
    name: build
    steps:
      - name: Check the app
        run: true
  e2e:
    name: e2e (${{ matrix.group }})
    steps:
      - name: Run e2e tests
        run: true
"""
GROUPS = '{"e2e": {"library": ["old.spec.js"], "reader": ["listed.spec.js"]}}\n'
CONFIG = """\
[plan_check]
specs = ["e2e/*.spec.js"]
groups = ["tests/groups.json"]
"""
POINTER = "1. workflow `check.yml`, job `{job}`, step `{step}`, greppable `{grep}`\n"
GOOD = {"job": "e2e (${{ matrix.group }})", "step": "Run e2e tests", "grep": "listed"}
SETTINGS = plancheckconfig.PlanCheck(
    specs=["e2e/*.spec.js"], groups=["tests/groups.json"]
)
OK = "Plan check: ok"


def repository(case: unittest.TestCase) -> diffrepo.Repository:
    """A repository whose ``origin/main`` has a workflow, a group file and a spec.

    Args:
        case: the test, whose end removes the repository.

    Returns:
        The repository, on a branch ``work`` that has not changed yet.
    """
    repo = diffrepo.make_repository(case)
    run_git(repo.root, "checkout", "-q", "main")
    diffrepo.commit(repo, ".github/workflows/check.yml", WORKFLOW)
    diffrepo.commit(repo, "tests/groups.json", GROUPS)
    diffrepo.commit(repo, "e2e/old.spec.js", "")
    run_git(repo.root, "update-ref", "refs/remotes/origin/main", "HEAD")
    run_git(repo.root, "checkout", "-q", "-B", "work")
    return repo


def serving(text: str) -> cipointercheck.Read:
    """A reader that gives the same text for every file.

    Args:
        text: the text.

    Returns:
        The reader.
    """
    return lambda _: text


def remove(repo: diffrepo.Repository, name: str) -> None:
    """Commit the removal of a file.

    Args:
        repo: the repository.
        name: the file's path.
    """
    run_git(repo.root, "rm", "-q", name)
    run_git(repo.root, *IDENTITY, "commit", "-q", "-m", f"remove {name}")


def check(repo: diffrepo.Repository, plan: str, table: str = CONFIG) -> world.Result:
    """Run ``pitboss plan-check`` on a Plan.

    Args:
        repo: the repository, whose ``work`` is the head.
        plan: the rows of the Plan.
        table: the text of the configuration.

    Returns:
        What it did.
    """
    return world.invoke(
        real_world(),
        "plan-check",
        write_text("body.txt", f"## Plan\n{plan}\n## Execution\nx\n"),
        "--repo",
        str(repo.root),
        "--head",
        "HEAD",
        "--config",
        write_text("project.toml", table),
    )


def verdict(repo: diffrepo.Repository, plan: str, said: str = OK) -> None:
    """Assert what a check of a Plan ends with, and that it exits as that says.

    Args:
        repo: the repository.
        plan: the rows of the Plan.
        said: the text its output must contain; ``Plan check: ok`` means that
            it passed, anything else that it was refused.
    """
    done = check(repo, plan)
    want = 0 if said == OK else 1
    assert_that([done.code, said in done.out], equal_to([want, True]))


def pointer(**names: str) -> str:
    """A pointer row that is right but for the names given.

    Args:
        **names: the job, step or greppable string to change.

    Returns:
        The row.
    """
    return POINTER.format(**{**GOOD, **names})


def accepts(
    case: unittest.TestCase,
    repo: diffrepo.Repository,
    field: str,
    values: Sequence[str],
) -> None:
    """Assert that a Plan passes with each of the values in a field of its pointer.

    Args:
        case: the test, which names each value.
        repo: the repository.
        field: ``job``, ``step`` or ``grep``.
        values: what the pointer gives there.
    """
    for given in values:
        with case.subTest(given):
            verdict(repo, pointer(**{field: given}))


class TestPointerAgainstTheTree(unittest.TestCase):
    """A pointer names a workflow, a job and a step that the file has."""

    def test_a_pointer_the_workflow_has_is_accepted(self) -> None:
        """Done-when: the accepted form, a job by its key or by its pattern."""
        accepts(self, repository(self), "job", ["e2e (${{ matrix.group }})", "e2e"])

    def test_a_step_the_file_does_not_have_is_refused_with_the_near_one(self) -> None:
        """Quire#1060: ``Run the e2e group`` is not the step ``Run e2e tests``."""
        said = (
            "ci-pointer: Plan line 2 gives the step `Run the e2e group`, which is no"
            " step of `.github/workflows/check.yml` (similar: `Run e2e tests`)"
        )
        verdict(repository(self), pointer(step="Run the e2e group"), said)

    def test_the_verdict_counts_the_findings(self) -> None:
        """The last line says how many CI pointer findings there are."""
        plan = pointer(step="Run the e2e group", job="e2e (settings)")
        verdict(repository(self), plan, "refused, CI pointer findings: 2")

    def test_a_job_name_is_matched_as_the_file_writes_it(self) -> None:
        """The matrix job's name with the group in it is not the file's pattern."""
        said = "gives the job `e2e (settings)`, which is no job"
        verdict(repository(self), pointer(job="e2e (settings)"), said)

    def test_a_workflow_file_at_neither_commit_is_refused(self) -> None:
        """A workflow that only the head has is accepted; one nobody has is not."""
        repo = repository(self)
        plan = "1. workflow `added.yml`, step `Go`\n"
        said = (
            "names the workflow `.github/workflows/added.yml`, which exists at"
            " neither the base nor the head"
        )
        verdict(repo, plan, said)
        added = "jobs:\n  a:\n    steps:\n    - name: Go\n"
        diffrepo.commit(repo, ".github/workflows/added.yml", added)
        verdict(repo, plan)

    def test_a_workflow_the_head_deleted_is_read_at_the_base(self) -> None:
        """The head has no file, the base's names stand."""
        repo = repository(self)
        remove(repo, ".github/workflows/check.yml")
        verdict(repo, pointer())


class TestSpecsTheDiffAdds(unittest.TestCase):
    """A spec the diff adds has a pointer and a group."""

    def test_a_spec_with_a_pointer_and_a_group_is_accepted(self) -> None:
        """The pointer's greppable string is the file name, or the path."""
        repo = repository(self)
        diffrepo.commit(repo, "e2e/listed.spec.js", "")
        accepts(self, repo, "grep", ["listed.spec.js", "e2e/listed.spec.js"])

    def test_a_spec_no_pointer_names_is_refused(self) -> None:
        """Quire#1060: the new spec had no CI pointer."""
        repo = repository(self)
        diffrepo.commit(repo, "e2e/listed.spec.js", "")
        said = (
            "the diff adds the spec `e2e/listed.spec.js`, which no CI pointer's"
            " greppable string names"
        )
        verdict(repo, pointer(), said)
        verdict(repo, "1. nothing points to CI\n", said)

    def test_a_spec_no_group_names_is_refused(self) -> None:
        """A spec that no CI job runs cannot be approved."""
        repo = repository(self)
        diffrepo.commit(repo, "e2e/unlisted.spec.js", "")
        said = (
            "the diff adds the spec `e2e/unlisted.spec.js`, which no group list"
            " file (`tests/groups.json`) names at the head"
        )
        verdict(repo, pointer(grep="unlisted.spec.js"), said)
        assert_that("no CI pointer's" in check(repo, pointer()).out, equal_to(True))

    def test_a_group_file_the_head_does_not_have_names_nothing(self) -> None:
        """The group list file is read at the head."""
        repo = repository(self)
        diffrepo.commit(repo, "e2e/listed.spec.js", "")
        remove(repo, "tests/groups.json")
        verdict(repo, pointer(grep="listed.spec.js"), "which no group list file")

    def test_what_is_not_a_spec_or_is_not_added_is_not_checked(self) -> None:
        """A helper in the directory, a spec in a subdirectory, a spec edited."""
        repo = repository(self)
        diffrepo.commit(repo, "e2e/helper.js", "")
        diffrepo.commit(repo, "e2e/sub/deep.spec.js", "")
        diffrepo.commit(repo, "e2e/old.spec.js", "changed\n")
        verdict(repo, "1. nothing points to CI\n")

    def test_no_table_checks_no_spec(self) -> None:
        """A configuration with no ``[plan_check]`` has no spec to hold."""
        repo = repository(self)
        diffrepo.commit(repo, "e2e/unlisted.spec.js", "")
        done = check(repo, "1. x\n", "[project]\n")
        assert_that([done.code, OK in done.out], equal_to([0, True]))

    def test_a_table_that_is_not_a_table_of_lists_is_a_usage_error(self) -> None:
        """The command says which key, and runs nothing."""
        repo = repository(self)
        for text, said in (
            ('plan_check = "x"\n', "[plan_check] must be a table"),
            ("[plan_check]\nspecs = 3\n", "specs must be a list of strings"),
            ("[plan_check]\ngroups = [1]\n", "groups must be a list of strings"),
        ):
            with self.subTest(text):
                done = check(repo, "1. x\n", text)
                assert_that([done.code, said in done.err], equal_to([2, True]))

    def test_a_configuration_that_is_not_there_is_a_usage_error(self) -> None:
        """The path is named."""
        path = "/nonexistent/project.toml"
        body = write_text("body.txt", "## Plan\n1. x\n")
        done = world.invoke(real_world(), "plan-check", body, "--config", path)
        assert_that([done.code, path in done.err], equal_to([2, True]))


class TestNames(unittest.TestCase):
    """The patterns and the group lists."""

    def test_a_pattern_matches_part_of_one_component(self) -> None:
        """No ``**``: the same number of components."""
        cases: Mapping[str, bool] = {
            "e2e/a.spec.js": True,
            "e2e/a.js": False,
            "e2e/sub/a.spec.js": False,
            "other/a.spec.js": False,
        }
        found = {
            path: cipointercheck.pattern_of(path, SETTINGS) is not None
            for path in cases
        }
        assert_that(found, equal_to(cases))

    def test_a_group_file_names_a_spec_by_path_or_by_name_under_its_directory(
        self,
    ) -> None:
        """JSON strings, at any depth; other text where the name stands alone."""
        cases = {
            '{"x": {"y": ["a.spec.js"]}}': True,
            '["e2e/a.spec.js"]': True,
            '{"a.spec.js.bak": 1, "n": 3, "t": true}': False,
            "a.spec.js\nb.spec.js\n": True,
            "xa.spec.js\n": False,
            "a.spec.jsx\n": False,
        }
        found = {
            text: cipointercheck.lists(text, "e2e/a.spec.js", "a.spec.js")
            for text in cases
        }
        assert_that(found, equal_to(cases))

    def test_a_pattern_with_a_wildcard_in_the_first_component_uses_the_path(
        self,
    ) -> None:
        """The name a group file gives is then the whole path, not the file name."""
        settings = dataclasses.replace(SETTINGS, specs=["*/a.spec.js"])
        named = cipointer.Pointer(
            line=1, workflow="w.yml", jobs=[], steps=[], greppable=["a.spec.js"]
        )
        found = {
            listed: len(
                cipointercheck.spec_findings(
                    ["x/a.spec.js"], [named], settings, serving(listed)
                )
            )
            for listed in ('["a.spec.js"]', '["x/a.spec.js"]')
        }
        assert_that(found, equal_to({'["a.spec.js"]': 1, '["x/a.spec.js"]': 0}))

    def test_a_spec_that_matches_no_pattern_has_its_own_path(self) -> None:
        """A path that is no spec is not asked for."""
        found = cipointercheck.spec_findings(["x/a.js"], [], SETTINGS, lambda _: None)
        assert_that(found, equal_to([]))
