"""Quorum-flavour acceptance tests: the repeat chain, driven through the graph.

Distinguishes the ongoing election instance from finished ones by the
`temporallyFinishedBy` bound on its `Chronoid` — not by list position — and
checks that a repeat APPENDS a successor while every prior instance, its
ballots and its votes survive.

Usage:
  uv run python tests/test_quorum.py cases/mayor-quorum
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


def main(argv: list[str]) -> int:
    case = (ROOT / (argv[1] if len(argv) > 1 else "cases/mayor-quorum")).resolve()
    c = OracleClient(case)
    fails: list[str] = []

    expect(fails, "repeat is a first-class ECA", "repeat" in c.eca_ids(), str(c.eca_ids()))

    # Initialised, not begun: the seed instance's Chronoid has no start bound.
    r0 = c.cycles()[0]
    from rdflib import URIRef
    started = c.graph.value(URIRef(chronoid_of(c, r0)), URIRef(GFO + "temporallyStartedBy"))
    expect(fails, "seed election is initialised (no start bound)", started is None, str(started))

    c.set_clock(0, 10)
    c.apply({"eca": "announce"})
    for who in (A, B, C):
        c.apply({"eca": "nominate", "citizen": who})
    c.set_clock(9, 10)
    c.apply({"eca": "prepare"})
    expect(fails, "r0 prepares ballots", len(c.ballots(r0)) == 21, str(len(c.ballots(r0))))  # 7 citizens x 3 candidates

    c.set_clock(10, 12)
    c.apply({"eca": "vote", "voter": A, "candidate": P + "citizen/bob"})
    c.set_clock(10, 20)
    c.apply({"eca": "count"})

    v = c.check()
    quorum = [x for x in v["violations"] if x["eca"] == "quorum"]
    expect(fails, "quorum fails with one vote of seven", len(quorum) == 1, str(v["violations"]))
    expect(fails, "quorum violation names the repeat date",
           any("repeat on day 40" in x.get("detail", "") for x in quorum), str(quorum))
    expect(fails, "repeat is pending on the authority",
           "repeat" in ecas_for(v, A), str(v["pending"]))

    subjects_before = c.subjects()
    c.apply({"eca": "repeat"})

    cycles = c.cycles()
    expect(fails, "repeat appends a successor", len(cycles) == 2, str([x.rsplit("/", 1)[-1] for x in cycles]))
    expect(fails, "successor is the higher cycleIndex",
           cycles[-1].endswith("r1"), cycles[-1])
    expect(fails, "prior instance is preserved", cycles[0] == r0, str(cycles))
    expect(fails, "no individual erased by the repeat",
           subjects_before <= c.subjects(), "subjects disappeared")

    # Finished vs ongoing, by Chronoid bounds rather than position.
    r1 = cycles[-1]
    from rdflib import URIRef as U
    fin0 = c.graph.value(U(chronoid_of(c, r0)), U(GFO + "temporallyFinishedBy"))
    fin1 = c.graph.value(U(chronoid_of(c, r1)), U(GFO + "temporallyFinishedBy"))
    expect(fails, "r0 carries a finish bound", fin0 is not None, str(fin0))
    expect(fails, "r1 is still open", fin1 is None, str(fin1))

    expect(fails, "r0 keeps its ballots", len(c.ballots(r0)) == 21, str(len(c.ballots(r0))))  # 7 citizens x 3 candidates
    expect(fails, "r0 keeps its vote", len(c.votes(r0)) == 1, str(len(c.votes(r0))))
    expect(fails, "r1 starts with a fresh registry", c.ballots(r1) == [], str(c.ballots(r1)))

    # The successor runs its own cycle at its OWN dates: r1 announces on day 30
    # (E=40, announce E-10), prepares on 39, and polls on 40. r0 keeps its own
    # day, so each instance is addressed explicitly rather than by a shared clock.
    c.set_clock(30, 10)
    expect(fails, "r1 opens its own nomination window",
           "nominate" in ecas_for(c.check(), A), str(c.check()["pending"]))
    c.apply({"eca": "nominate", "citizen": B})
    c.apply({"eca": "nominate", "citizen": C})
    c.set_clock(39, 10)
    c.apply({"eca": "prepare"})
    expect(fails, "r1 prepares citizen x candidate ballots",
           len(c.ballots(r1)) == 14, str(len(c.ballots(r1))))  # 7 citizens x 2 candidates
    expect(fails, "r0 untouched by r1's prepare", len(c.ballots(r0)) == 21, str(len(c.ballots(r0))))

    # A repeat on a still-void cycle chains again.
    c.set_clock(40, 10)
    c.apply({"eca": "vote", "voter": A, "candidate": P + "citizen/bob"})
    c.set_clock(40, 20)
    c.apply({"eca": "count"})
    c.apply({"eca": "repeat"})
    expect(fails, "repeat chains to a third cycle", len(c.cycles()) == 3,
           str([x.rsplit("/", 1)[-1] for x in c.cycles()]))

    # Repeat is refused when the quorum held.
    try:
        c.apply({"eca": "repeat"})
        expect(fails, "reject repeat on valid quorum", False, "act was accepted")
    except OracleRejected as e:
        expect(fails, "reject repeat on valid quorum", "quorum" in str(e), str(e))

    print(f"\n{'all pass' if not fails else f'{len(fails)} FAILURES: {fails}'}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
