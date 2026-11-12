quire's `.github/workflows/canonical-files.yml` calls repository-prototype's `canonical-files-check.yml` by commit, with the same commit repeated as `tools-ref`. `.github/workflows/relock.yml` lists neither in `workflow-pins` or `pin-copies` (read at main e9d6bbe), so the daily relock never moves them. The pin sat at 3d26060, 107 commits older than the template for the `Review churn tests` step (repository-prototype#679, ef9f4f0), and `canonical-files / canonical-files` fails with `.github/workflows/check.yml: not canonical` on quire#1110, quire#1115 and quire#1116 (run 43155811995, job 130975349650 for quire#1116). quire#1116 moves the pin by hand (to ef9f4f0); this ticket makes the relock move it.

## Done when

- `bats-lang/repository-prototype/.github/workflows/canonical-files-check.yml` is in the `workflow-pins` of `.github/workflows/relock.yml`, and `canonical-files.yml`'s `tools-ref` is in its `pin-copies`, demonstrated by `grep -n 'canonical-files-check.yml' .github/workflows/relock.yml` printing both lines.
- A relock run on the head shows the pin moved, demonstrated by the `### Workflow pins` rows of the next relock pull request body naming `canonical-files-check.yml`.

Not in this ticket: a check that fails when any pinned workflow is missing from the relock list (a ticket in bats-lang/bats, `check-pins`, filed beside this one).
