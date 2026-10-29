import sys
R = "plugins/pitboss/skills/sweep/references/"
rows = [
 ("CLAUDE.md 1 research, not the human (split)", "rules.md", "No task is ever \"left to the human\""),
 ("CLAUDE.md 1 judgement after research", "rules.md", "Judgement is what is left after the research"),
 ("CLAUDE.md 1 nothing comparable found", "rules.md", "if nothing comparable can be found, say so"),
 ("CLAUDE.md 2 a proof is a static proof (split)", "engineering.md", "it means a static proof"),
 ("CLAUDE.md 2 only tested is said tested", "engineering.md", "A claim that is\nonly tested"),
 ("CLAUDE.md 3 comments name area by keyword (pitboss)", "engineering.md", "names the area by keyword"),
 ("CLAUDE.md 4 names are words (split)", "engineering.md", "named by what they are, in words"),
 ("CLAUDE.md 4 loop index exception", "engineering.md", "A loop index"),
 ("CLAUDE.md 5 p0 (split)", "rules.md", "**p0:** anything that makes CI faster"),
 ("CLAUDE.md 5 p1", "rules.md", "**p1: correctness.**"),
 ("CLAUDE.md 5 p2", "rules.md", "**p2:** the project's user-visible"),
 ("CLAUDE.md 5 p3", "rules.md", "**p3:** everything else"),
 ("CLAUDE.md 5 order of work 1 to 5", "rules.md", "**Order of work.**"),
 ("CLAUDE.md 5 no downgrades", "rules.md", "**No downgrades without the owner's word.**"),
 ("CLAUDE.md 6 no shell / own language (split)", "engineering.md", "We do not write shell scripts"),
 ("CLAUDE.md 6 run: step is code we wrote", "ci.md", "is code we wrote"),
 ("CLAUDE.md 6 no mtimes (engineering)", "engineering.md", "**No mtimes in freshness.**"),
 ("CLAUDE.md 6 no mtimes (ci)", "ci.md", "## No mtimes in freshness"),
 ("CLAUDE.md 7 four dated quotes (split)", "rules.md", "THERE ARE RULES ABOUT BREAKING CHANGES"),
 ("CLAUDE.md 7 p2 per dependent, blocked", "rules.md", "File the tickets against the\n  dependents as p2"),
 ("CLAUDE.md 7 filed-when is never a finding", "rules.md", "Who cares when it was filed"),
 ("CLAUDE.md 7 review checks both steps", "rules.md", "**The review of such a pull request checks both steps"),
 ("CLAUDE.md 8 CI pinned (split)", "ci.md", "Every input to CI is pinned in the source"),
 ("CLAUDE.md 8 no bot opens PRs", "ci.md", "I don't want these bots opening PRs"),
 ("CLAUDE.md 9 cache judged by tool (split)", "ci.md", "A restored cache is judged by the tool"),
 ("CLAUDE.md 10 check locally before push (split)", "ci.md", "Run the project's check before every push"),
 ("CLAUDE.md 10 sample with printed seed", "ci.md", "**A run over a population is a sample.**"),
 ("CLAUDE.md 10 checkout stays", "rules.md", "The check before a push runs in a checkout that stays"),
 ("CLAUDE.md 11 evidence for every claim (split)", "rules.md", "**The author posts the evidence for every claim"),
 ("CLAUDE.md 11 red test root-caused", "rules.md", "**A test that went red is root-caused"),
 ("CLAUDE.md 11 author owns CI", "rules.md", "**The author owns CI until it is green**"),
 ("CLAUDE.md 11 reviewer on green exact head", "rules.md", "starts only when every required check is finished and green on\n  the exact head"),
 ("CLAUDE.md 12 version is the commit's (split)", "engineering.md", "A project's version is the date of the commit"),
 ("backup-errors.md every error says what to do (split)", "engineering.md", "**Every error says what to do.**"),
 ("ci.md draft bullet (split)", "ci.md", "## A draft PR runs no costly job"),
 ("ci.md population is a sample bullet", "ci.md", "**A run over a population is a sample.**"),
 ("e2e.md no real-time wait bullet (split)", "engineering.md", "## A test never waits in real time"),
 ("e2e.md machine matches CI paragraph", "rules.md", "never a reason for a spec to be skipped"),
 ("interface.md failures said, never dropped (split)", "engineering.md", "**Failures are said, never dropped.**"),
 ("release.md first sentence (split)", "engineering.md", "## A version is the commit's, never the build's"),
 ("sync.md every outcome said, unexpected as such (split)", "engineering.md", "**Every outcome is said, and the unexpected as such.**"),
 ("types.md a choice is a datatype (split)", "engineering.md", "An int never encodes one of a fixed set of cases"),
]
import re
for name, f, phrase in rows:
    text = open(R + f).read()
    m = re.search(r"\s+".join(re.escape(w) for w in phrase.split()), text)
    if not m:
        print("MISSING", name); sys.exit(1)
    i = m.start()
    line = text.count("\n", 0, i) + 1
    heads = list(re.finditer(r"^## .*$", text[:m.end()], re.M))
    print(f"{name} -> {f}:{line} under {heads[-1].group(0) if heads else '(title)'}")

# What each inventory row says stays in quire must not be in the pitboss files.
stays = [
 ("CLAUDE.md 1", "The quality rules below"),
 ("CLAUDE.md 1", "the e2e suite"),
 ("CLAUDE.md 2", "Trusted primitives"),
 ("CLAUDE.md 2", "$UNSAFE"),
 ("CLAUDE.md 4", "search-close"),
 ("CLAUDE.md 4", "toc-row12"),
 ("CLAUDE.md 4", "numbered-id prefixes"),
 ("CLAUDE.md 5", "The Android release"),
 ("CLAUDE.md 6", "quire#623"),
 ("CLAUDE.md 6", "quire#635"),
 ("CLAUDE.md 6", "alarm clock"),
 ("CLAUDE.md 6", "Anything a second app would copy"),
 ("CLAUDE.md 7", "orchestration.md"),
 ("CLAUDE.md 7", "guidelines.py"),
 ("CLAUDE.md 7", "repository-prototype's CLAUDE.md"),
 ("CLAUDE.md 8", "bats.lock"),
 ("CLAUDE.md 8", ".github/bats-version"),
 ("CLAUDE.md 8", "android.yml@"),
 ("CLAUDE.md 8", "Dependabot"),
 ("CLAUDE.md 8", "#996"),
 ("CLAUDE.md 9", "quire-<name>@<commit>"),
 ("CLAUDE.md 9", "bats stamp"),
 ("CLAUDE.md 10", "bats check"),
 ("CLAUDE.md 10", "qsweep"),
 ("CLAUDE.md 10", "10 to 15 minutes"),
 ("CLAUDE.md 11", ".claude/agents"),
 ("CLAUDE.md 12", "release.md"),
 ("CLAUDE.md 13", "play-internal"),
 ("CLAUDE.md 13", "Google Play"),
 ("backup-errors.md", "notice.bats"),
 ("backup-errors.md", "Reopen Quire"),
 ("backup-errors.md", "Copy details"),
 ("e2e.md", "clickControl"),
 ("e2e.md", "rawMouse"),
 ("e2e.md", "Playwright"),
 ("interface.md", "ui.bats"),
 ("interface.md", "Trash"),
 ("sync.md", "Nextcloud"),
 ("sync.md", "GOOGLE_ANSWER_MS"),
 ("types.md", "lincloptr1"),
 ("types.md", "datavtype"),
 ("release.md", "YEAR.MONTH.DAY.SECONDS"),
 ("release.md", "versionCode"),
]
for name, phrase in stays:
    for f in ("rules.md", "engineering.md", "ci.md"):
        text = open(R + f).read()
        if phrase in text:
            print("STAYS-IN-QUIRE FOUND", name, repr(phrase), f)
            sys.exit(1)
    print(f"absent from rules.md, engineering.md, ci.md: {name}: {phrase!r}")
