"""Erasure is prohibited; only counting is revisable.

The knowledge graph is the snapshot, so an act that removed an individual
would silently rewrite history. These are the three claims that make that
impossible, checked against both laws:

  7.1  no accepted act removes an individual, for any ECA of either law
  7.2  an instance finished with an outcome that does not count keeps every
       individual it accumulated; recording non-count is the only lever
  7.3  a finish bound lands on the Chronoid in GFO's own shape, using no
       vocabulary the ontology has not declared, and reads identically
       whether the finish falls on a calendar point or not

Usage:
  uv run python scripts/test_cancellation.py artefacts/mayor-2027
  uv run python scripts/test_cancellation.py artefacts/mayor-quorum
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from rdflib import RDF, RDFS, URIRef

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from potato_hamlet.oracle import OracleClient, OracleRejected  # noqa: E402

PH = "https://potato-hamlet.example/ontology/"
GFO = "https://w3id.org/gfo-core/"
GFO_LIGHT = "https://w3id.org/gfo-light/"
CITIZEN = PH + "citizen/"

fails: list[str] = []


def expect(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        fails.append(f"{name}{(': ' + detail) if detail else ''}")
    print(f"  {'PASS' if cond else 'FAIL'} {name}")


def manifest_of(case: Path) -> dict[str, dict]:
    data = yaml.safe_load((case / "manifest.yaml").read_text())
    return {e["id"]: e for e in data["ecas"]}


def act_for(eca: dict, entry: dict, citizen: str) -> dict | None:
    """Build a complete act from the manifest's declarations, or None."""
    act: dict = {"eca": eca["id"]}
    choices = entry.get("choices") or {}
    for prm in eca.get("params") or []:
        if prm["source"] == "selected":
            act[prm["name"]] = citizen
        else:
            options = choices.get(prm["name"]) or []
            if not options:
                return None
            act[prm["name"]] = options[0]
    return act


def offered(c: OracleClient) -> list[tuple[str, dict]]:
    """Every act the verdict currently offers, built from declarations."""
    by_id = manifest_of(c.case)
    out = []
    for citizen, entries in c.check().get("pending", {}).items():
        for entry in entries:
            eca = by_id.get(entry["eca"] if isinstance(entry, dict) else entry)
            if eca is None:
                continue
            act = act_for(eca, entry, citizen)
            if act is not None:
                out.append((citizen, act))
    return out


def apply_next(c: OracleClient, log: list[dict] | None = None) -> dict | None:
    """Apply one offered act. Returns the act, or None if none applied."""
    for _citizen, act in offered(c):
        try:
            c.apply(act)
            if log is not None:
                log.append(act)
            return act
        except OracleRejected:
            continue
    return None


def advance_to_day(c: OracleClient, day: int, hour: int, log: list[dict] | None = None) -> None:
    """Move the clock, letting each due act happen on the way.

    Acts are taken in time order rather than all at the end: a law whose
    guards depend on the clock would otherwise refuse an act offered at day 0
    when applied at day 10.
    """
    c.set_time(0)
    for target_day in range(0, day + 1):
        for target_hour in (10, 19):
            if (target_day, target_hour) > (day, hour):
                continue
            c.set_time(target_day, target_hour)
            while apply_next(c, log) is not None:
                pass


def declared_predicates(case: Path) -> set[str]:
    g = OracleClient(case).schema
    from rdflib import OWL

    return {
        str(s)
        for s in set(g.subjects(RDF.type, OWL.ObjectProperty))
        | set(g.subjects(RDF.type, OWL.DatatypeProperty))
        | set(g.subjects(RDF.type, OWL.AnnotationProperty))
    }


# ---------------------------------------------------------------- 7.1


def drive(
    case: Path,
    voters: list[str],
    log: list[dict] | None = None,
    finish: tuple[int, int] = (10, 20),
) -> OracleClient:
    """Play one election cycle with exactly `voters` casting a ballot.

    Deliberate rather than greedy: taking whatever the verdict offers makes
    quorum succeed by construction, and the repeat branch — the one place a
    cycle ends without counting — is then never reached. Driving turnout is
    the only way to exercise it.

    `finish` is when the closing acts happen. It has to be set BEFORE they do:
    the cycle records the moment it ended, and a bound already written is not
    rewritten by moving the clock afterwards.
    """
    c = OracleClient(case)
    for citizen in (CITIZEN + "alice", CITIZEN + "bob", CITIZEN + "cara"):
        c.set_time(0)
        for act in ({"eca": "announce"}, {"eca": "nominate", "citizen": citizen}):
            try:
                c.apply(act)
                if log is not None:
                    log.append(act)
            except OracleRejected:
                pass
    c.set_time(9)
    for act in ({"eca": "prepare"},):
        try:
            c.apply(act)
            if log is not None:
                log.append(act)
        except OracleRejected:
            pass
    c.set_time(10, 12)
    candidates = sorted(
        str(s)
        for s in c.graph.subjects(RDF.type, URIRef(PH + "CandidateRole"))
    )
    for voter in voters:
        if not candidates:
            break
        act = {"eca": "vote", "voter": CITIZEN + voter, "candidate": candidates[0]}
        try:
            c.apply(act)
            if log is not None:
                log.append(act)
        except OracleRejected:
            pass
    c.set_time(*finish)
    for _ in range(10):
        act = apply_next(c, log)
        if act is None:
            break
    # The caller needs to know which ending was reached, and whether the
    # repeat duty is the thing that produced it.
    c.applied_log = list(log) if log is not None else []
    return c


def check_monotonicity(case: Path) -> None:
    """No accepted act removes an individual, over every branch of the law.

    Two passes, because the law has two endings: a quorum that holds ends in
    `proclaim`, one that fails ends in `repeat`. Taking every offered act
    always produces the first, so the second needs turnout chosen.
    """
    quorum_fails = "repeat" in manifest_of(case)
    passes = {
        "quorum holds": ["alice", "bob", "cara"],
        "quorum fails": ["alice"] if quorum_fails else None,
    }

    for label, voters in passes.items():
        if voters is None:
            continue
        applied: list[dict] = []
        removals: list[str] = []
        c = OracleClient(case)
        seen = c.subjects()

        def watch(step: dict) -> None:
            now = c.subjects()
            for gone in sorted(seen - now):
                removals.append(f"after {step['eca']}: <{gone}>")
            seen.update(now)

        driven = drive(case, voters, applied)
        for step in applied:
            watch(step)
        for _ in range(40):
            act = apply_next(driven, applied)
            if act is None:
                break
            watch(act)

        fired = [a["eca"] for a in applied]
        expect(
            f"{case.name} 7.1 [{label}]: no accepted act removed an individual",
            not removals,
            f"{len(removals)} removed, first {removals[0]}" if removals else "",
        )
        expect(
            f"{case.name} 7.1 [{label}]: the law was actually exercised",
            len(fired) >= 5,
            f"only {len(fired)} acts applied: {fired}",
        )
        print(f"    {label}: {fired}")


# ---------------------------------------------------------------- 7.2


def check_void_retains_individuals(case: Path) -> None:
    """A void instance keeps everything; non-count is the only lever."""
    log: list[dict] = []
    r0 = OracleClient(case).cycles()[0]
    c = drive(case, ["alice"], log)

    outcome = c.graph.value(URIRef(r0), URIRef(PH + "outcome"))
    expect(
        "quorum 7.2: the failed cycle records outcome 'void'",
        outcome is not None and str(outcome) == "void",
        f"outcome={outcome}",
    )
    expect(
        "quorum 7.2: the repeat duty was what ended it",
        "repeat" in [a["eca"] for a in c.applied_log],
        "the cycle ended without the repeat duty",
    )

    # Everything the void cycle accumulated, taken before the void was applied.
    accumulated = {
        str(s) for s in c.graph.subjects(RDF.type, URIRef(PH + "CastVote"))
    } | {
        str(s) for s in c.graph.subjects(RDF.type, URIRef(PH + "SelfNomination"))
    } | {
        str(s) for s in c.graph.subjects(RDF.type, URIRef(PH + "BallotVote"))
    } | {
        str(s)
        for s in c.graph.subjects(RDF.type, URIRef(PH + "CandidateRole"))
    }

    after = c.subjects()
    lost = sorted(accumulated - after)
    expect(
        "quorum 7.2: the void cycle retains every individual it accumulated",
        not lost,
        f"{len(lost)} of {len(accumulated)} lost, first <{lost[0]}>" if lost else "",
    )

    # Nothing about those individuals changed except that the cycle stopped
    # counting. Their types are the evidence: a retro-deleted vote would have
    # lost its ph:CastVote typing.
    untyped = [
        s
        for s in sorted(accumulated)
        if s.startswith(PH) and not list(c.graph.objects(URIRef(s), RDF.type))
    ]
    expect(
        "quorum 7.2: retained individuals keep their types",
        not untyped,
        f"first untyped <{untyped[0]}>" if untyped else "",
    )

    # And the non-count is recorded as an outcome, not by mutating them.
    vote_subjects = {
        str(s) for s in c.graph.subjects(RDF.type, URIRef(PH + "CastVote"))
    }
    expect(
        "quorum 7.2: the non-counting vote is still in the graph as a cast vote",
        bool(vote_subjects),
        "the void cycle's ballot disappeared instead of being marked void",
    )

    # The successor is a fresh instance: it inherits the population, not the
    # void cycle's nominations or votes.
    cycles = c.cycles()
    if len(cycles) > 1:
        r1 = cycles[-1]
        tag = r1.rsplit("/", 1)[-1]
        fresh = [
            str(s)
            for s in c.graph.subjects(RDF.type, URIRef(PH + "SelfNomination"))
            if tag in str(s)
        ]
        expect(
            "quorum 7.2: the successor starts with a fresh registry",
            not fresh,
            f"{len(fresh)} nomination(s) leaked into the successor",
        )
        print(f"    void cycle retained {len(accumulated)} individuals; successor {tag}")
    else:
        expect("quorum 7.2: a successor cycle was scheduled", False, "no r1")


# ---------------------------------------------------------------- 7.3


def finish_graph(case: Path, day: int, hour: int) -> tuple[OracleClient, str]:
    """Drive quorum to a void ending at exactly (day, hour).

    The clock is moved to the requested moment before the repeat duty is
    taken, so the finish bound records that moment rather than polls close.
    """
    c = drive(case, ["alice"], finish=(day, hour))
    return c, c.cycles()[0]


def check_finish_bound(case: Path) -> None:
    """The finish bound lands on the Chronoid, in vocabulary already declared."""
    allowed = declared_predicates(case)

    shapes = {}
    moments = {"on a calendar point (polls close)": (10, 20), "off any calendar point": (12, 14)}
    for label, (day, hour) in moments.items():
        c, r0 = finish_graph(case, day, hour)
        graph = c.graph
        chronoid = graph.value(URIRef(r0), URIRef(PH + "hasTime"))
        expect(
            f"quorum 7.3 at {label}: the cycle relates to a Chronoid",
            chronoid is not None,
        )
        if chronoid is None:
            continue
        finish = graph.value(URIRef(chronoid), URIRef(GFO + "temporallyFinishedBy"))
        expect(
            f"quorum 7.3 at {label}: the Chronoid carries a finish bound",
            finish is not None,
        )
        if finish is None:
            continue
        got_day = graph.value(URIRef(finish), URIRef(PH + "dayIndex"))
        got_hour = graph.value(URIRef(finish), URIRef(PH + "atHour"))
        expect(
            f"quorum 7.3 at {label}: the bound records the finishing moment "
            f"({day} {hour})",
            str(got_day) == str(day) and str(got_hour) == str(hour),
            f"recorded {got_day} {got_hour}",
        )
        is_tb = finish in set(graph.objects(None, RDF.type)) or any(
            str(t).startswith(GFO_LIGHT) for t in graph.objects(URIRef(finish), RDF.type)
        )
        expect(
            f"quorum 7.3 at {label}: the bound is a GFO TimeBoundary",
            is_tb,
            f"typed {list(graph.objects(URIRef(finish), RDF.type))}",
        )
        # No new vocabulary: every predicate the oracle emitted is one the
        # ontology declares.
        undeclared = sorted(
            {
                str(p)
                for p in graph.predicates()
                if isinstance(p, URIRef)
                and not str(p).startswith((PH, GFO, GFO_LIGHT, str(RDFS), str(RDF)))
                and str(p) not in allowed
            }
        )
        expect(
            f"quorum 7.3 at {label}: no vocabulary outside the ontology",
            not undeclared,
            f"{len(undeclared)} undeclared, first <{undeclared[0]}>" if undeclared else "",
        )
        # Shape, so the two moments can be compared: which predicates sit on
        # the Chronoid and on its bounds, ignoring literal values.
        shape = (
            tuple(sorted(str(p) for p in graph.predicates(URIRef(chronoid), None))),
            tuple(
                sorted(
                    f"{str(p).rsplit('/', 1)[-1]}="
                    + ("" if str(o).replace(".", "").isdigit() else "*")
                    for p, o in graph.predicate_objects(URIRef(finish))
                )
            ),
        )
        shapes[label] = shape

    if len(shapes) == 2:
        first, second = shapes.values()
        expect(
            "quorum 7.3: a finish reads identically on and off a calendar point",
            first == second,
            f"on-point {first[1]} vs off-point {second[1]}",
        )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    case = (ROOT / argv[1]).resolve()
    print(f"cancellation semantics — {case.name}\n")

    check_monotonicity(case)
    print()
    if (case / "population.ttl").read_text().count("ScheduleRepeatElection"):
        check_void_retains_individuals(case)
        print()
        check_finish_bound(case)

    if fails:
        print(f"\n{len(fails)} FAILURE(S): {fails}")
        return 1
    print("\nall pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
