"""Tests for the names of a workflow file (keyword: ci-pointer, pitboss#335)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import ciworkflow

QUIRE = """\
name: check
on:
  push:
    branches: [main]
env:
  A: b
jobs:
  plan:
    runs-on: ubuntu-24.04
    steps:
      - name: Every test in exactly one group
        run: echo "- name: not a step"
      - uses: actions/checkout@v4
        name: What this run has to run
    timeout-minutes: 5
  static:
    name: static (${{ matrix.group }})
    runs-on: ubuntu-24.04
    strategy:
      matrix:
        include:
          - name: not a step either
            group: a
    steps:
    - name: Static tests # a comment
      run: true
    - name: "Quoted step"
      run: true
  e2e:
    name: 'e2e (${{ matrix.group }})'
    steps:
      # - name: commented out
      - name: Run e2e tests
        with:
          list:
            - name: nested item
"""


class TestWorkflow(unittest.TestCase):
    """The jobs and steps a file names, as written."""

    def test_the_jobs_are_keys_and_names(self) -> None:
        """A matrix job's name is its pattern."""
        assert_that(
            sorted(ciworkflow.read(QUIRE).jobs),
            equal_to(
                [
                    "e2e",
                    "e2e (${{ matrix.group }})",
                    "plan",
                    "static",
                    "static (${{ matrix.group }})",
                ]
            ),
        )

    def test_the_steps_are_the_list_items_of_steps(self) -> None:
        """A name in a string, a matrix or a nested list is no step."""
        assert_that(
            sorted(ciworkflow.read(QUIRE).steps),
            equal_to(
                [
                    "Every test in exactly one group",
                    "Quoted step",
                    "Run e2e tests",
                    "Static tests",
                    "What this run has to run",
                ]
            ),
        )

    def test_a_file_with_no_jobs_names_nothing(self) -> None:
        """No ``jobs:``, or an empty one."""
        for text in ("", "name: x\non: push\n", "jobs:\nname: y\n"):
            with self.subTest(text):
                found = ciworkflow.read(text)
                assert_that([set(found.jobs), set(found.steps)], equal_to([set()] * 2))
