"""Pending/apply conformance: every pending act applies clean, non-pending rejects.

Acts are derived from the manifest's DECLARED parameters plus the choices the
verdict supplies, never from a hardcoded table — that is the point: if the
driver needed per-law knowledge to build an act, the declarations would not be
doing their job. Guards against `pendingOf`/`apply` drift (design risk 1).

Usage:
  uv run python scripts/test_conformance.py artefacts/mayor-2027
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from rdflib import OWL, RDF, RDFS, Graph, URIRef  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from potato_hamlet.oracle import OracleClient, OracleRejected  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lawdriver import advance  # noqa: E402

P = "https://potato-hamlet.example/ontology/"
A, B, C = P + "citizen/alice", P + "citizen/bob", P + "citizen/cara"


def act_from_declaration(eca: dict, pending_choices: dict) -> dict:
    """Build an act from the manifest's declared parameters.

    A parameter sourced `selected` binds to the acting citizen; one sourced
    `choices` takes the first option the verdict offered. Nothing here knows
    which law it is driving.
    """
    act: dict = {"eca": eca["id"]}
    for param in eca.get("params") or []:
        name, source = param["name"], param["source"]
        if source == "selected":
            act[name] = pending_choices["selected"]
        elif source == "choices":
            options = pending_choices.get(name) or []
            if not options:
                raise ValueError(f"{eca['id']}.{name} is sourced 'choices' but no options were offered")
            act[name] = options[0]
    return act


def main(argv: list[str]) -> int:
    case = (ROOT / (argv[1] if len(argv) > 1 else "artefacts/mayor-2027")).resolve()
    manifest = yaml.safe_load((case / "manifest.yaml").read_text())
    by_id = {e["id"]: e for e in manifest["ecas"]}
    fails: list[str] = []

    def expect(name: str, cond: bool, detail: str = ""):
        print(("PASS " if cond else "FAIL ") + name + (f" ({detail})" if detail and not cond else ""))
        if not cond:
            fails.append(name)

    def fresh() -> OracleClient:
        return OracleClient(case)

    def _declared_classes(case_dir: Path) -> set[str]:
        g = Graph()
        g.parse(case_dir / "ontology.ttl")
        return {str(s) for s in g.subjects(RDFS.subClassOf, None)} | {
            str(s) for s in g.subjects(RDF.type, OWL.Class)
        }

    def entry_choices(entry: dict) -> dict:
        """Choice slots the verdict offers for one pending entry."""
        return entry.get("choices") or {}

    # Every ECA declares its params, so an act can always be built.
    missing = [i for i, e in by_id.items() if "holder_role" not in e or "params" not in e]
    expect("every ECA declares holder_role and params", not missing, str(missing))

    def announced_and_nominated(c: OracleClient):
        """Reach a state with duties outstanding, by playing acts.

        Not a hardcoded sequence: which ECAs exist, and what they need, is the
        law's business. The manifest declares the parameters and the verdict
        supplies the choices, so this works for any law -- and doubles as a
        check that they are sufficient on their own.
        """
        advance(c, case, rounds=2)

    def ballots_exist(c: OracleClient):
        """Drive further, so a decision is reachable."""
        advance(c, case, rounds=4)

    # A scenario table is inherently about one law's days and its ECAs, so it
    # runs only where those ECAs exist. Everything ABOVE it -- the declarations,
    # the choice slots, the act round trip -- is law-agnostic and runs always.
    if "announce" in by_id and "vote" in by_id:
        scenarios = [
            ("announce-day", 0, 10, ["announce", "nominate"], None),
            ("nominate-window", 5, 10, ["nominate"], None),
            ("prepare-day", 9, 10, ["prepare"], announced_and_nominated),
            ("polls-open", 10, 12, ["vote"], ballots_exist),
            ("polls-closed", 10, 20, ["vote", "count"], ballots_exist),
            ("count-due", 11, 10, ["count"], ballots_exist),
        ]
        for name, day, hour, expect_fired, setup in scenarios:
            c2 = fresh()
            if setup is not None:
                setup(c2)
            c2.set_time(day, hour)
            v2 = c2.check()
            expect(f"{name}: fires {expect_fired}", sorted(v2["fired"]) == sorted(expect_fired),
                   str(v2["fired"]))
            offered = 0
            for citizen, entries in v2.get("pending", {}).items():
                for entry in entries:
                    eca_id = entry["eca"] if isinstance(entry, dict) else entry
                    eca = by_id.get(eca_id)
                    if eca is None:
                        continue
                    choices = {"selected": citizen, **entry_choices(entry)}
                    act = act_from_declaration(eca, choices)
                    if act is None:
                        continue
                    try:
                        c2.apply(act)
                        offered += 1
                    except (OracleRejected, ValueError) as e:
                        expect(f"{name}: apply {eca_id}", False, str(e))
                        break
            expect(f"{name}: {offered} pending acts all apply", offered > 0, "no acts offered")

    # Representative non-pending acts must be rejected, and the rejection must
    # name a guard. Fixtures are given as (label, act, expected fragment), and
    # only those naming an ECA this law actually declares are run -- otherwise
    # the suite would be asserting mayor behaviour on a requisitions law.
    fixtures = [
        ("vote-when-closed", {"eca": "vote", "voter": A, "candidate": B}, "polls closed"),
        ("nominate-when-closed", {"eca": "nominate", "citizen": A}, "registry closed"),
        ("proclaim-with-no-candidacy", {"eca": "proclaim"}, "no candidates"),
        ("announce-when-not-due", {"eca": "announce"}, "not due"),
        ("settle-without-an-instance", {"eca": "settle", "officer": A,
                                       "requisition": "https://potato-hamlet.example/ontology/requisition/nobody",
                                       "decision": "approved"}, "unknown requisition"),
    ]
    for label, act, fragment in fixtures:
        if act["eca"] not in by_id:
            continue
        # Only meaningful when the act is NOT due right now. When to reject is
        # the law's business, so ask the verdict instead of hardcoding a day.
        guard = OracleClient(case)
        if act["eca"] in guard.check()["fired"]:
            continue
        before = guard.subjects()
        try:
            guard.apply(act)
            expect(f"{label} rejects", False, "the act was accepted")
        except OracleRejected as e:
            expect(f"{label} rejects", fragment in str(e), str(e))
            expect(f"{label} leaves the graph unchanged", guard.subjects() == before)

    # ---- readings: a law's results without a verdict field of their own ----
    # `wouldWin` named one process's result, so a taxation or requisition law
    # had nothing to put there and any new result needed a verdict change. A
    # reading names a law-chosen id, a kind from a closed set, and a value.
    # A reading is ABSENT when the law has no such result, so what must hold is
    # that every reading emitted is meaningful -- never a null standing in for
    # an absent one. `null` is the failure this replaces.
    seed_readings = fresh().check()["readings"]
    expect(
        "no reading carries a null value",
        all(r.get("value") is not None for r in seed_readings),
        str(seed_readings),
    )
    expect(
        "a `ref` reading carries no null value either",
        all(r.get("value") is not None for r in seed_readings if r.get("kind") == "ref"),
        str(seed_readings),
    )
    expect("the verdict no longer carries wouldWin",
           "wouldWin" not in fresh().check())

    c = fresh()
    ballots_exist(c)
    for _ in range(30):
        v = c.check()
        offered = [
            (citizen, entry)
            for citizen, entries in v.get("pending", {}).items()
            for entry in entries
        ]
        moved = False
        for citizen, entry in offered:
            eca = by_id.get(entry["eca"])
            if eca is None:
                continue
            act = act_from_declaration(eca, {"selected": citizen, **entry_choices(entry)})
            if act is None:
                continue
            try:
                c.apply(act)
                moved = True
                break
            except (OracleRejected, ValueError):
                continue
        if not moved:
            break

    readings = c.check()["readings"]
    kinds = {r.get("kind") for r in readings}
    expect(
        "every reading names an id, a kind from the closed set, and a value",
        bool(readings)
        and all(
            r.get("id") and r.get("kind") in {"decimal", "ref", "flag"} and "value" in r
            for r in readings
        ),
        str(readings),
    )

    refs = [r for r in readings if r.get("kind") == "ref"]
    expect("a ref reading names the ontology class it points at",
           all(r.get("refClass") for r in refs), str(refs))
    undeclared = sorted(
        {r["refClass"] for r in refs
         if r.get("refClass") not in _declared_classes(case)}
    )
    expect("every refClass is a class the ontology declares",
           not undeclared, str(undeclared))

    # A ref reading resolves: its value is an IRI in the graph, and its label
    # comes back through the declared class rather than a second source.
    resolved = []
    for r in refs:
        node = URIRef(r["value"])
        if (node, RDF.type, URIRef(r["refClass"])) in c.graph:
            label = c.graph.value(node, URIRef("https://potato-hamlet.example/ontology/label"))
            resolved.append(label is not None)
    expect("a ref reading resolves to a labelled individual of its refClass",
           bool(refs) and all(resolved) and len(resolved) == len(refs), str(refs))

    decimals = [r for r in readings if r.get("kind") == "decimal"]
    expect("a law reporting a number and a law reporting a citizen differ only in "
           "id, kind, and value",
           bool(decimals) and bool(refs),
           f"kinds seen: {sorted(kinds)}")

    # ---- witnesses: structured, and interpretable without knowing the law --
    # Flattened `witnessCitizen`/`witnessCandidate` fields meant only a consumer
    # that already knew the law could read a violation, and a violation about a
    # COUNT rather than a pair of individuals had nowhere to put it. The quorum
    # failure was that case: nulls for both fields, counts only inside `detail`.
    v = c.check()
    expect("no violation carries a flattened witness field",
           all("witnessCitizen" not in x and "witnessCandidate" not in x
               for x in v["violations"]), str(v["violations"]))
    expect("every violation carries a structured witness",
           all(isinstance(x.get("witness"), dict) for x in v["violations"]),
           str(v["violations"]))
    expect("a witness has refs and counts",
           all(isinstance(x["witness"].get("refs"), list)
               and isinstance(x["witness"].get("counts"), list)
               for x in v["violations"]), str(v["violations"]))
    expect("every named count gives a name and a value",
           all(isinstance(cn.get("name"), str) and isinstance(cn.get("value"), int)
               for x in v["violations"] for cn in x["witness"]["counts"]),
           str(v["violations"]))
    expect("every ref is an IRI present in the graph",
           all(URIRef(r) in c.graph.subjects(RDF.type, None)
               for x in v["violations"] for r in x["witness"]["refs"]),
           str(v["violations"]))

    if "repeat" in by_id:  # the quorum flavour
        # One voter of three fails quorum, so the count witness must appear in
        # the structured fields and not only in the display string.
        q = fresh()
        for who in (A, B, C):
            # announce is a once-per-cycle duty: set the clock inside the loop
            # so the position is rewritten, not the announcement repeated.
            q.set_time(0)
            try:
                q.apply({"eca": "announce"})
            except OracleRejected:
                pass
            q.apply({"eca": "nominate", "citizen": who})
        q.set_time(9)
        q.apply({"eca": "prepare"})
        q.set_time(10, 12)
        entry = next(
            e for es in q.check()["pending"].values() for e in es if e["eca"] == "vote"
        )
        q.apply({"eca": "vote", "voter": A,
                 "candidate": entry["choices"]["candidate"][0]})
        q.set_time(10, 20)
        q.apply({"eca": "count"})
        qv = q.check()
        quorum = next((x for x in qv["violations"] if x["eca"] == "quorum"), None)
        expect("a failed quorum reports a violation", quorum is not None,
               str(qv["violations"]))
        if quorum:
            counts = {cn["name"]: cn["value"] for cn in quorum["witness"]["counts"]}
            expect("the quorum witness gives voted and total as counts",
                   counts == {"voted": 1, "total": 3}, str(counts))
            expect("the quorum witness names who did not turn out",
                   sorted(r.rsplit("/", 1)[-1] for r in quorum["witness"]["refs"])
                   == ["bob", "cara"], str(quorum["witness"]["refs"]))
            expect("the counts survive outside the display string",
                   "1 voted of 3" in quorum["detail"]
                   and counts.get("voted") == 1, quorum["detail"])

    # ---- process attribution: every duty names the instance it belongs to --
    # Without it, two duties that look alike are indistinguishable and a
    # consumer cannot group them under the process they serve.
    # At the seed, where duties exist. Checking at a driven-forward state would
    # be vacuous for the flat law, which has nothing pending once counted.
    seed = fresh()
    entries = [e for es in seed.check().get("pending", {}).values() for e in es]
    expect("every pending entry names a process instance",
           bool(entries) and all(e.get("process") for e in entries), str(entries))
    # A duty on an instance that EXISTS must name one that is in the graph. A
    # duty that CREATES one may name an instance not yet minted -- that is what
    # the ECA's `mints` declaration is for, and it is the only licence to name
    # something absent.
    mints = {e.get("mints") for e in manifest["ecas"] if e.get("mints")}
    creating = {e["id"] for e in manifest["ecas"] if e.get("mints")}
    existing = [e for e in entries if e["eca"] not in creating]
    expect("a duty on an existing instance names one that is in the graph",
           all(URIRef(e["process"]) in seed.graph.subjects(RDF.type, None)
               for e in existing),
           str([e.get("process") for e in existing]))
    expect("a duty on an existing instance names one typed by a declared class",
           all(
               any(str(t) in _declared_classes(case)
                   for t in seed.graph.objects(URIRef(e["process"]), RDF.type))
               for e in existing
           ),
           str([e["process"] for e in existing]))
    expect("a creating ECA declares the class it mints",
           all("https://potato-hamlet.example/ontology/" + m in _declared_classes(case)
           for m in mints),
           str(mints))

    if "repeat" in by_id:  # the quorum flavour, where instances accumulate
        # After a repeat the graph holds two instances, and no duty may name the
        # finished one: it is history, and history is visible to past-dependent
        # rules rather than something a fresh duty is owed on.
        r = fresh()
        for who in (A, B, C):
            r.set_time(0)
            try:
                r.apply({"eca": "announce"})
            except OracleRejected:
                pass
            r.apply({"eca": "nominate", "citizen": who})
        r.set_time(9)
        r.apply({"eca": "prepare"})
        r.set_time(10, 12)
        e = next(x for es in r.check()["pending"].values() for x in es if x["eca"] == "vote")
        r.apply({"eca": "vote", "voter": A, "candidate": e["choices"]["candidate"][0]})
        r.set_time(10, 20)
        r.apply({"eca": "count"})
        before = [x for _cit, es in r.check()["pending"].items() for x in es]
        expect("before the repeat, duties name the cycle that is current",
               bool(before) and len({x["process"] for x in before}) == 1,
               str([(x["eca"], x["process"]) for x in before]))
        r.apply({"eca": "repeat"})
        instances = r.cycles()
        expect("the repeat leaves two instances in the graph",
               len(instances) == 2, str(instances))
        r.set_time(40, 10)
        after = [x for _cit, es in r.check()["pending"].items() for x in es]
        expect("after the repeat, duties name the new instance and never the finished one",
               all(x["process"] == instances[-1] for x in after),
               str([(x["eca"], x["process"]) for x in after]))

    print(f"\n{'all pass' if not fails else f'{len(fails)} FAILURES: {fails}'}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
