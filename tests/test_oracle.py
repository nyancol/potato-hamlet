"""Oracle acceptance tests, driven through the instance graph.

The knowledge graph is the snapshot: every fixture is the law's own
`population.ttl` advanced with acts, never a hand-written state object. That
is the point of these tests — they exercise the same path a consumer does.

Usage:
  uv run python tests/test_oracle.py cases/mayor-2027
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from runtime.oracle import (  # noqa: E402
    RDF_TYPE,
    OracleClient,
    OracleRejected,
    URIRef,
    iri,
)

P = "https://potato-hamlet.example/ontology/"
A, B, C = P + "citizen/alice", P + "citizen/bob", P + "citizen/cara"
# The union world: elections run with all seven citizens, so plays that must
# cover the hamlet (deliver) iterate over ALL while plays about the
# nominated (nominate, vote, tie) stay on A, B, C.
D, E, F, G = (P + "citizen/ada", P + "citizen/barnaby", P + "citizen/cleo",
              P + "citizen/dara")
ALL = (A, B, C, D, E, F, G)
HAMLET = P + "hamlet"


def ecas_for(verdict, citizen):
    """ECAs pending for one citizen; each entry is an object naming its ECA."""
    return [e["eca"] if isinstance(e, dict) else e for e in verdict["pending"].get(citizen, [])]


def expect(fails: list[str], name: str, cond: bool, detail: str = ""):
    print(("PASS " if cond else "FAIL ") + name + (f" ({detail})" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def main(argv: list[str]) -> int:
    case = (ROOT / (argv[1] if len(argv) > 1 else "cases/mayor-2027")).resolve()
    c = OracleClient(case)
    fails: list[str] = []

    # 1. list matches manifest eca ids.
    import yaml
    manifest_ids = [e["id"] for e in yaml.safe_load((case / "manifest.yaml").read_text())["ecas"]]
    expect(fails, "list==manifest", c.eca_ids() == manifest_ids,
           f"{c.eca_ids()} vs {manifest_ids}")

    # 2. Fallback authority: with no mayor, the oldest citizen (Alice, 71)
    #    holds announce on the announce day.
    c.set_clock(0, 10)
    v = c.check()
    expect(fails, "announce on oldest", "announce" in ecas_for(v, A), str(v["pending"]))
    expect(fails, "nominate offered to each citizen",
           all("nominate" in ecas_for(v, x) for x in (A, B, C)), str(v["pending"]))

    # 3. Full cycle through the graph: announce -> nominate -> prepare ->
    #    vote -> count -> proclaim, with the office changing only at proclaim.
    c.apply({"eca": "announce"})
    for who in (A, B, C):
        c.apply({"eca": "nominate", "citizen": who})
    expect(fails, "nominations complete the pending list",
           all("nominate" not in ecas_for(c.check(), x) for x in (A, B, C)),
           str(c.check()["pending"]))
    expect(fails, "candidacy follows nomination",
           sorted(x.rsplit("/", 1)[-1] for x in c.occupants("CandidateRole")) == ["alice", "bob", "cara"],
           str(c.occupants("CandidateRole")))

    c.set_clock(9, 10)
    c.apply({"eca": "prepare"})
    expect(fails, "prepare makes citizen x candidate ballots", len(c.ballots()) == 21,
           str(len(c.ballots())))  # 7 citizens x 3 candidates

    # Two mayor flavours ship, and they differ in whether making and delivering
    # are one duty or two. `mayor-quorum` states them separately (law.txt:11-12)
    # and serves a `deliver`; `mayor-2027` does not, and still delivers as part of
    # preparing. The suite runs against both, so which shape it asserts is read
    # off the oracle rather than assumed -- otherwise the flavour that has been
    # rewritten fails the suite for the rewrite.
    if "deliver" in c.eca_ids():
        expect(fails, "each ballot is a distinct sheet",
               len({r["sheet"] for r in c.ballot_records()}) == 21,
               str(len({r["sheet"] for r in c.ballot_records()})))
        expect(fails, "prepare mints no sheet of its own",
               len(list(c.graph.subjects(RDF_TYPE, iri("Sheet")))) == 49,
               str(len(list(c.graph.subjects(RDF_TYPE, iri("Sheet"))))))  # 7 citizens x 7 sheets
        expect(fails, "each sheet is marked with its candidate's name",
               all(r["marked"] for r in c.ballot_records()),
               str([(r["sheet"], r["marked"]) for r in c.ballot_records()][:2]))

        # The state BETWEEN the two duties is the point of splitting them: papers
        # written and not yet carried. So the distribution violation is expected
        # here, and its witness names the citizen whose mailbox is still empty.
        expect(fails, "made-but-undelivered still reports distribution",
               [x for x in c.check()["violations"] if x["eca"] == "all_distributed"],
               str(c.check()["violations"]))
        expect(fails, "the witness names the undelivered citizen",
               [x["witness"]["refs"][0] for x in c.check()["violations"]
                if x["eca"] == "all_distributed"][0] in ("ada", D),
               str([x["witness"] for x in c.check()["violations"]]))
        expect(fails, "the witness also names the ballot's own individual",
               any(r.endswith(("ada-1", "alice-1", "bob-1", "cara-1"))
                   for x in c.check()["violations"] if x["eca"] == "all_distributed"
                   for r in x["witness"]["refs"]),
               str([x["witness"] for x in c.check()["violations"]]))
        expect(fails, "nothing is delivered before the delivering act",
               not any(r["mailbox"] for r in c.ballot_records()),
               str([r["mailbox"] for r in c.ballot_records()][:3]))

        for who in ALL:
            c.apply({"eca": "deliver", "recipient": who})
        expect(fails, "deliver puts every ballot in a mailbox",
               all(r["mailbox"] for r in c.ballot_records()),
               str([(r["sheet"], r["mailbox"]) for r in c.ballot_records()][:3]))
        expect(fails, "each ballot reached its OWNER's mailbox",
               all(r["mailbox"] == c.mailbox_of(r["owner"]) for r in c.ballot_records()),
               str([(r["owner"], r["mailbox"]) for r in c.ballot_records()][:3]))
    else:
        expect(fails, "this flavour delivers as part of preparing",
               not [x for x in c.check()["violations"] if x["eca"] == "all_distributed"],
               str(c.check()["violations"]))
    expect(fails, "no distribution violation once delivered",
           not [x for x in c.check()["violations"] if x["eca"] == "all_distributed"],
           str(c.check()["violations"]))

    # A 1-1 tie: Bob (54) beats Cara (43) on oldest, and only two citizens
    # vote, so the tie is real rather than an artefact of an odd electorate.
    c.set_clock(10, 12)
    for voter, cand in [(A, B), (B, C)]:
        c.apply({"eca": "vote", "voter": voter, "candidate": cand})
    expect(fails, "votes recorded", len(c.votes()) == 2, str(len(c.votes())))

    # A cast vote is a `ph:Deposit`, so the paper's whereabouts are recorded with
    # the shared `ph:placedIn` -- the first user that relation has in any law. It
    # goes on the SHEET, because that is the physical fact, and on exactly the
    # citizen's own ballot for the candidate they voted for. Only the rewritten
    # flavour declares and records a box; `mayor-2027` has no seeded one.
    if "deliver" in c.eca_ids():
        box = [str(s) for s in c.graph.subjects(RDF_TYPE, iri("BallotBox"))]
        expect(fails, "the law's world has one ballot box", len(box) == 1, str(box))
        if box:
            voted = {(r["owner"], r["candidate"]): r["sheet"]
                      for r in c.ballot_records() if r["owner"] in (A, B)}
            placed = {r["sheet"] for r in c.ballot_records()
                      if str(c.graph.value(URIRef(r["sheet"]), iri("placedIn")) or "") in box}
            expect(fails, "each vote put exactly its own ballot in the box",
                   placed == {voted[(A, B)], voted[(B, C)]},
                   f"placed={sorted(placed)} "
                   f"expected={sorted([voted[(A, B)], voted[(B, C)]])}")
            expect(fails, "no other ballot went into the box",
                   len(placed) == 2, str(sorted(placed)))

    # The double-vote guard is only reachable while polls are open.
    try:
        c.apply({"eca": "vote", "voter": A, "candidate": C})
        expect(fails, "reject double vote", False, "act was accepted")
    except OracleRejected as e:
        expect(fails, "reject double vote", "already voted" in str(e), str(e))

    c.set_clock(10, 20)
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
    expect(fails, "ballots survive the whole cycle", len(c.ballots()) == 21, str(len(c.ballots())))
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

    # 6. An act that declares what it acts on refuses when the world lacks it.
    # `vote` declares the ballot box by name (`acts_on` in the manifest), so with
    # the box gone the act must refuse rather than record a vote that reached
    # nothing -- which would let the quorum be counted from ballots no one ever
    # put anywhere. Driven on a fresh client so the cycle above is untouched.
    if "deliver" in c.eca_ids():
        d = OracleClient(ROOT / "cases" / "mayor-quorum")
        box = next(d.graph.subjects(RDF_TYPE, iri("BallotBox")), None)
        expect(fails, "scratch seed has a ballot box to remove", box is not None, "none")
        if box is not None:
            for pred, obj in list(d.graph.predicate_objects(box)):
                d.graph.remove((box, pred, obj))
            for who in (A, B, C):
                d.apply({"eca": "nominate", "citizen": who})
            d.set_clock(9, 10)
            d.apply({"eca": "prepare"})
            for who in (A, B, C):
                d.apply({"eca": "deliver", "recipient": who})
            d.set_clock(10, 12)
            try:
                d.apply({"eca": "vote", "voter": A, "candidate": B})
                expect(fails, "vote refuses with no ballot box", False, "act was accepted")
            except OracleRejected as e:
                expect(fails, "vote refuses with no ballot box", "ballot box" in str(e), str(e))
            expect(fails, "the refusal recorded no vote", len(d.votes()) == 0, str(d.votes()))

    print(f"\n{'all pass' if not fails else f'{len(fails)} FAILURES: {fails}'}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
