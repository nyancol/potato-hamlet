"""Revocation-flavour acceptance test: withdraw-halt-postpone, driven through the graph.

Covers the full path — nominate, vote, revoke during polls, halt, successor
scheduled — including that no act removes an individual and that the successor
starts from a fresh registry. Also covers the boundary races: revoke after
polls-close is refused, double withdrawal is refused, and withdrawing the only
candidate still halts rather than producing an empty count.

Usage:
  uv run python tests/test_revocation.py cases/mayor-revocation
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from runtime.oracle import OracleClient, OracleRejected  # noqa: E402

P = "https://potato-hamlet.example/ontology/"
A, B, C = P + "citizen/alice", P + "citizen/bob", P + "citizen/cara"
GFO = "https://w3id.org/gfo-core/"


def ecas_for(verdict, citizen):
    return [e["eca"] if isinstance(e, dict) else e for e in verdict["pending"].get(citizen, [])]


def expect(fails: list[str], name: str, cond: bool, detail: str = ""):
    print(("PASS " if cond else "FAIL ") + name + (f" ({detail})" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def chronoid_of(c: OracleClient, cycle: str) -> str:
    from rdflib import URIRef
    return str(c.graph.value(URIRef(cycle), URIRef(P + "hasTime")))


def outcome_of(c: OracleClient, cycle: str) -> str | None:
    from rdflib import URIRef
    v = c.graph.value(URIRef(cycle), URIRef(P + "outcome"))
    return str(v) if v is not None else None


def finish_of(c: OracleClient, cycle: str):
    from rdflib import URIRef as U
    fin = c.graph.value(U(chronoid_of(c, cycle)), U(GFO + "temporallyFinishedBy"))
    if fin is None:
        return None
    d = c.graph.value(fin, U(P + "dayIndex"))
    h = c.graph.value(fin, U(P + "atHour"))
    return (int(str(d)), int(str(h)))


def main(argv: list[str]) -> int:
    case = (ROOT / (argv[1] if len(argv) > 1 else "cases/mayor-revocation")).resolve()
    c = OracleClient(case)
    fails: list[str] = []

    ids = c.eca_ids()
    for eca in ("revoke", "halt", "postpone"):
        expect(fails, f"{eca} is a first-class ECA", eca in ids, str(ids))

    r0 = c.cycles()[0]
    c.set_clock(0, 10)
    c.apply({"eca": "announce"})
    for who in (A, B, C):
        c.apply({"eca": "nominate", "citizen": who})
    c.set_clock(9, 10)
    c.apply({"eca": "prepare"})
    expect(fails, "r0 prepares ballots", len(c.ballots(r0)) == 21, str(len(c.ballots(r0))))

    c.set_clock(10, 12)
    c.apply({"eca": "vote", "voter": A, "candidate": B})
    expect(fails, "r0 records the vote", len(c.votes(r0)) == 1, str(c.votes(r0)))

    # Revoke outside polls is refused: drive a fresh client before announce.
    early = OracleClient(case)
    early.set_clock(0, 10)
    early.apply({"eca": "announce"})
    early.apply({"eca": "nominate", "citizen": B})
    try:
        early.apply({"eca": "revoke", "citizen": B})
        expect(fails, "reject revoke outside polls", False, "act was accepted")
    except OracleRejected as e:
        expect(fails, "reject revoke outside polls", "poll" in str(e).lower(), str(e))

    # The revocation: a registered candidate withdraws during polls.
    c.apply({"eca": "revoke", "citizen": B})
    v = c.check()
    halts = [x for x in v["violations"] if x["eca"] == "halt"]
    expect(fails, "halt violation names the withdrawn candidate under refs",
           any(B in (x.get("witness") or {}).get("refs", []) for x in halts), str(halts))
    expect(fails, "halt pends on the authority",
           "halt" in ecas_for(v, A), str(v["pending"]))

    subjects_before = c.subjects()
    ballots_before = len(c.ballots(r0))
    votes_before = len(c.votes(r0))
    c.apply({"eca": "halt"})
    expect(fails, "halt stamps the outcome as stopped",
           outcome_of(c, r0) == "stopped", str(outcome_of(c, r0)))
    fin = finish_of(c, r0)
    expect(fails, "halt lands the finish bound inside the election-day span",
           fin is not None and fin[0] == 10 and 9 <= fin[1] < 19, str(fin))
    expect(fails, "stopped instance keeps every ballot",
           len(c.ballots(r0)) == ballots_before, f"{len(c.ballots(r0))} vs {ballots_before}")
    expect(fails, "stopped instance keeps every vote with a non-count outcome",
           len(c.votes(r0)) == votes_before and outcome_of(c, r0) == "stopped",
           f"votes={c.votes(r0)} outcome={outcome_of(c, r0)}")
    expect(fails, "no act removes an individual",
           subjects_before <= c.subjects(), "subjects disappeared")
    readings = {r["id"]: r for r in c.check().get("readings", [])}
    expect(fails, "halt reading is emitted", "halted" in readings, str(list(readings)))

    # A second halt is refused; counting a stopped instance is refused.
    try:
        c.apply({"eca": "halt"})
        expect(fails, "reject second halt", False, "act was accepted")
    except OracleRejected:
        expect(fails, "reject second halt", True)
    try:
        c.set_clock(10, 20)
        c.apply({"eca": "count"})
        expect(fails, "reject count on stopped instance", False, "act was accepted")
    except OracleRejected:
        expect(fails, "reject count on stopped instance", True)
    c.set_clock(10, 12)

    c.apply({"eca": "postpone"})
    cycles = c.cycles()
    expect(fails, "postpone appends a successor", len(cycles) == 2, str(cycles))
    r1 = cycles[-1]
    expect(fails, "prior instance is preserved", cycles[0] == r0, str(cycles))
    expect(fails, "no act removes an individual on postpone",
           subjects_before <= c.subjects(), "subjects disappeared")
    expect(fails, "successor starts with a fresh registry",
           c.ballots(r1) == [] and c.occupants("CandidateRole", r1) == [],
           f"ballots={c.ballots(r1)} candidates={c.occupants('CandidateRole', r1)}")
    expect(fails, "r0 still stopped after postpone",
           outcome_of(c, r0) == "stopped", str(outcome_of(c, r0)))

    # Boundary: revoke after polls-close is refused.
    c.set_clock(30, 10)
    c.apply({"eca": "announce"})
    c.apply({"eca": "nominate", "citizen": B})
    c.apply({"eca": "nominate", "citizen": C})
    c.set_clock(39, 10)
    c.apply({"eca": "prepare"})
    c.set_clock(40, 20)
    try:
        c.apply({"eca": "revoke", "citizen": B})
        expect(fails, "reject revoke after polls-close", False, "act was accepted")
    except OracleRejected as e:
        expect(fails, "reject revoke after polls-close", "poll" in str(e).lower(), str(e))
    # Back inside the window the same revoke is accepted, then a double is refused.
    c.set_clock(40, 12)
    c.apply({"eca": "revoke", "citizen": B})
    try:
        c.apply({"eca": "revoke", "citizen": B})
        expect(fails, "reject double withdrawal", False, "act was accepted")
    except OracleRejected as e:
        expect(fails, "reject double withdrawal", "withdraw" in str(e).lower(), str(e))

    # Boundary: withdrawing the only candidate still halts.
    solo = OracleClient(case)
    solo.set_clock(0, 10)
    solo.apply({"eca": "announce"})
    solo.apply({"eca": "nominate", "citizen": B})
    solo.set_clock(9, 10)
    solo.apply({"eca": "prepare"})
    solo.set_clock(10, 12)
    solo.apply({"eca": "revoke", "citizen": B})
    solo.apply({"eca": "halt"})
    sr0 = solo.cycles()[0]
    expect(fails, "single-candidate withdrawal still halts",
           outcome_of(solo, sr0) == "stopped", str(outcome_of(solo, sr0)))
    solo.apply({"eca": "postpone"})
    expect(fails, "single-candidate halt postpones to a fresh cycle",
           len(solo.cycles()) == 2 and solo.ballots(solo.cycles()[-1]) == [],
           str(solo.cycles()))

    print(f"\n{'all pass' if not fails else f'{len(fails)} FAILURES: {fails}'}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
