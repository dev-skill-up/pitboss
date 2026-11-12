quire's `canonical-files-check.yml` pin (a `uses: bats-lang/repository-prototype/.github/workflows/canonical-files-check.yml@<40 hex>` line) was in no `workflow-pins` list of `relock.yml`, so the daily relock never moved it and it went 107 commits stale (quire#1118; it blocked quire#1110, quire#1115 and quire#1116). `bats check-pins` (area `.claude/rules/check-pins.md`, #390) judges floating inputs but does not compare the pins in `.github` against the relock caller's lists.

## Done when

- `bats check-pins` fails for a repository that has `uses: bats-lang/<repo>/<path>@<40 hex>` of a `bats-lang` workflow or action that `.github/workflows/relock.yml` lists in neither `workflow-pins` nor another list the shared relock reads, naming the file, the line and the missing list, demonstrated by a fixture under `tests/` that has the pin and no list entry and whose expected output is that failure.
- The same run passes on a fixture whose pin is in `workflow-pins`, demonstrated by a second fixture that expects exit 0.

Found by quire#1118.
