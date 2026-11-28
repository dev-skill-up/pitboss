import unittest

from hamcrest import assert_that, equal_to

from .. import actions, machine, parse

SHA = "a" * 40
T = frozenset({"MEMBER"})


def pr(draft=False, state="clean", runs=("success",), comments=()):
    data = {"number": 7, "head": {"sha": SHA}, "draft": draft, "mergeable_state": state,
            "labels": [], "body": "Fixes #3"}
    rs = [{"status": "completed", "conclusion": c} for c in runs]
    cs = [{"body": b, "author_association": "MEMBER"} for b in comments]
    return parse.pull(data, rs, cs, T)


APPROVED = f"Adversarial review\nReviewed: {SHA}\nPlan: approved\nVerdict: approved"
REJECTED = f"Adversarial review\nReviewed: {SHA}\nVerdict: changes needed"


class Fake:
    def __init__(self):
        self.calls = []

    def merge(self, n): self.calls.append(("merge", n))
    def undraft(self, n): self.calls.append(("undraft", n))
    def comment(self, n, b): self.calls.append(("comment", n))


class TestMachine(unittest.TestCase):
    def test_steps(self):
        S = machine.Step
        for p, want in [
            (pr(), S.REVIEW),
            (pr(comments=[APPROVED]), S.MERGE),
            (pr(draft=True, comments=[APPROVED]), S.UNDRAFT),
            (pr(runs=("success", "failure"), comments=[APPROVED]), S.FIX_CI),
            (pr(runs=("success",), state="dirty", comments=[APPROVED]), S.FIX_CONFLICT),
            (pr(comments=[REJECTED]), S.WORKER),
            (pr(comments=[REJECTED, REJECTED]), S.OPUS_RULING),
            (pr(comments=["Ruling: escalate"]), S.OWNER),
        ]:
            assert_that(machine.pull_step(p), equal_to(want))

    def test_pending_waits(self):
        p = parse.pull({"number": 1, "head": {"sha": SHA}, "labels": []},
                       [{"status": "in_progress"}], [{"body": APPROVED, "author_association": "MEMBER"}], T)
        assert_that(machine.pull_step(p), equal_to(machine.Step.WAIT))

    def test_untrusted_comment_ignored(self):
        p = parse.pull({"number": 1, "head": {"sha": SHA}, "labels": []}, [],
                       [{"body": APPROVED, "author_association": "NONE"}], T)
        assert_that(machine.pull_step(p), equal_to(machine.Step.REVIEW))

    def test_ticket(self):
        t = parse.ticket({"number": 3, "state": "open", "labels": [], "body": "x\n## Done when\n- a\n- b"})
        assert_that(t.done_when, equal_to(("a", "b")))
        assert_that(machine.ticket_step(t, [pr()]), equal_to(machine.Step.WAIT_FOR_PR))
        assert_that(machine.ticket_step(t, []), equal_to(machine.Step.OPEN_PR))
        closed = parse.ticket({"number": 3, "state": "closed", "labels": []})
        assert_that(machine.ticket_step(closed, []), equal_to(machine.Step.DONE))


class TestActions(unittest.TestCase):
    def test_merge_checks_state(self):
        hub = Fake()
        assert_that(actions.merge(hub, pr()), equal_to(actions.Refused(machine.Step.MERGE, machine.Step.REVIEW)))
        assert_that(hub.calls, equal_to([]))
        assert_that(actions.merge(hub, pr(comments=[APPROVED])), equal_to(actions.Done("merged")))
        assert_that(hub.calls, equal_to([("merge", 7)]))

    def test_undraft(self):
        hub = Fake()
        assert_that(actions.undraft(hub, pr(draft=True, comments=[APPROVED])), equal_to(actions.Done("undrafted")))
        assert_that(actions.undraft(hub, pr(comments=[APPROVED])).__class__, equal_to(actions.Refused))
