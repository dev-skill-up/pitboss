Blocks bats-lang/quire#1115 (quire#1113), so it has 1115's age and priority. Quire's `check.yml` is a byte-exact template (`tools/pin-audit/templates/check-quire.yml`), and `canonical-files` is red on quire#1115 because its `check.yml` differs from it. By the overlap rule the new form is added beside the current one, and the current one is kept for one cycle (the pattern of repository-prototype#679, whose old form is `check-quire-before-review-churn.yml`).

What quire#1115 changes in `check.yml`: the queue job gets the output `run_id` and a step `The queue run's number`; the app check moves from `build` into a job of its own, `checked`; `static` needs `checked`; `e2e` and `android` need `checked` and `build`; `check` needs both; the merge group uploads the artifact `static-memo-<group>` and the main push after the queue passed downloads it and saves it as main's cache.

Done-when:

- `tools/pin-audit/templates/check-quire.yml` is the text of quire's `check.yml` at the head of quire#1115 with the template's holes, and the current text is kept as `check-quire-before-memo-transfer.yml`: demonstrated by `bats test` in `tools/pin-audit` passing with a test that plants each of the two forms and passes both, and a test that plants a `check.yml` equal to neither and fails.
- Quire's `check.yml` at the head of quire#1115 passes `canonical-files`: demonstrated by `pin_audit --repository quire` run on a checkout of that head exiting 0.
- A p2 ticket that removes `check-quire-before-memo-transfer.yml` once quire#1115 has merged exists: demonstrated by its number in the pull request body.
