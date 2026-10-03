"""Oracle acceptance tests, driven through the instance graph.

The knowledge graph is the snapshot: every fixture is the law's own
`population.ttl` advanced with acts, never a hand-written state object. That
is the point of these tests — they exercise the same path a consumer does.

Usage:
  uv run python scripts/test_oracle.py artefacts/mayor-2027
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from potato_hamlet.oracle import OracleClient, OracleRejected  # noqa: E402

P = "https://potato-hamlet.example/ontology/"
A, B, C = P + "citizen/alice", P + "citizen/bob", P + "citizen/cara"
HAMLET = P + "hamlet"


def ecas_for(verdict, citizen):
    """ECAs pending for one citizen; each entry is an object naming its ECA."""
    return [e["eca"] if isinstance(e, dict) else e for e in verdict["pending"].get(citizen, [])]


def expect(fails: list[str], name: str, cond: bool, detail: str = ""):
    print(("PASS " if cond else "FAIL ") + name + (f" ({detail})" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def main(argv: list[str]) -> int:
    case = (ROOT / (argv[1] if len(argv) > 1 else "artefacts/mayor-2027")).resolve()
    c = OracleClient(case)
    fails: list[str] = []

    # 1. list matches manifest eca ids.
    import yaml
    manifest_ids = [e["id"] for e in yaml.safe_load((case / "manifest.yaml").read_text())["ecas"]]
    expect(fails, "list==manifest", c.eca_ids() == manifest_ids,
           f"{c.eca_ids()} vs {manifest_ids}")

    # 2. Fallback authority: with no mayor, the oldest citizen (Alice, 71)
    #    holds announce on the announce day.
    c.set_time(0)
    v = c.check()
    expect(fails, "announce on oldest", "announce" in ecas_for(v, A), str(v["pending"]))
    expect(fails, "nominate offered to each citizen",
           all("nominate" in ecas_for(v, x) for x in (A, B, C)), str(v["pending"]))

    # 3. Full cycle through the graph: announce -> nominate -> prepare ->
    #    vote -> count -> proclaim, with the office changing only at proclaim.
    c.apply({"eca": "announce"})
    for who in (A, B, C):
        c.apply({"eca": "nominate", "citizen": who})
    expect(fails, "nominations complete the pending list", not c.check()["pending"],
           str(c.check()["pending"]))
    expect(fails, "candidacy follows nomination",
           sorted(x.rsplit("/", 1)[-1] for x in c.occupants("CandidateRole")) == ["alice", "bob", "cara"],
           str(c.occupants("CandidateRole")))

    c.set_time(9)
    c.apply({"eca": "prepare"})
    expect(fails, "prepare distributes citizen x candidate ballots", len(c.ballots()) == 9,
           str(len(c.ballots())))
    expect(fails, "no distribution violation once prepared",
           not [x for x in c.check()["violations"] if x["eca"] == "all_distributed"],
           str(c.check()["violations"]))

    # A 1-1 tie: Bob (54) beats Cara (43) on oldest, and only two citizens
    # vote, so the tie is real rather than an artefact of an odd electorate.
    c.set_time(10, 12)
    for voter, cand in [(A, B), (B, C)]:
        c.apply({"eca": "vote", "voter": voter, "candidate": cand})
    expect(fails, "votes recorded", len(c.votes()) == 2, str(len(c.votes())))

    # The double-vote guard is only reachable while polls are open.
    try:
        c.apply({"eca": "vote", "voter": A, "candidate": C})
        expect(fails, "reject double vote", False, "act was accepted")
    except OracleRejected as e:
        expect(fails, "reject double vote", "already voted" in str(e), str(e))

    c.set_time(10, 20)
    c.apply({"eca": "count"})
    v = c.check()
    # The winner is a `ref` reading now, not a verdict field: the reading names
    # the ontology class so a consumer resolves the label without knowing the law.
    winner = next((r for r in v["readings"] if r["id"] == "mayor"), None)
    expect(fails, "tie resolves to the older candidate",
           winner is not None and winner["value"] == B, str(v["readings"]))
    expect(fails, "the winner reading names the individual's class",
           winner is not None and winner.get("refClass") == P + "Citizen", str(winner))
    expect(fails, "proclaim still pending on the authority",
           "proclaim" in ecas_for(v, A), str(v["pending"]))
    expect(fails, "office unfilled until proclaim",
           c.occupants("MayorRole", HAMLET) == [], str(c.occupants("MayorRole", HAMLET)))

    c.apply({"eca": "proclaim"})
    expect(fails, "proclaim fills the office",
           c.occupants("MayorRole", HAMLET) == [B], str(c.occupants("MayorRole", HAMLET)))
    expect(fails, "phase reaches ResultsPosted", c.check()["phase"] == "ResultsPosted",
           c.check()["phase"])

    # 4. Nothing was erased: every ballot and vote from earlier is still there.
    expect(fails, "ballots survive the whole cycle", len(c.ballots()) == 9, str(len(c.ballots())))
    expect(fails, "votes survive the whole cycle", len(c.votes()) == 2, str(len(c.votes())))

    # 5. Guards reject with a named reason, and rejection leaves the graph alone.
    before = c.subjects()
    for name, act, fragment in [
        ("out-of-window nominate", {"eca": "nominate", "citizen": A}, "registry closed"),
        ("double announce", {"eca": "announce"}, "not due"),
        ("repeat when quorum valid", {"eca": "repeat"}, "quorum not failed"),
    ]:
        if act["eca"] not in c.eca_ids():
            continue
        try:
            c.apply(act)
            expect(fails, f"reject {name}", False, "act was accepted")
        except OracleRejected as e:
            expect(fails, f"reject {name}", fragment in str(e), str(e))
    expect(fails, "rejection leaves the graph unchanged", c.subjects() == before, "graph changed")

    print(f"\n{'all pass' if not fails else f'{len(fails)} FAILURES: {fails}'}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
