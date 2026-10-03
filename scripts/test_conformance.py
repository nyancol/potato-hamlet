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
        """Announce, then take every citizen's nomination.

        The graph starts empty, so a scenario must reach its own state by
        playing acts — the old fixtures seeded `candidates` directly, which
        the graph cannot do. Each scenario stops at the last act it is meant
        to exercise, so the act under test is still pending.
        """
        c.set_time(0)
        c.apply({"eca": "announce"})
        for who in (A, B, C):
            c.apply({"eca": "nominate", "citizen": who})

    def ballots_exist(c: OracleClient):
        announced_and_nominated(c)
        c.set_time(9)
        c.apply({"eca": "prepare"})

    scenarios = [
        ("announce-day", 0, 10, ["announce", "nominate"], None),
        ("nominate-window", 5, 10, ["nominate"], None),
        ("prepare-day", 9, 10, ["prepare"], announced_and_nominated),
        ("polls-open", 10, 12, ["vote"], ballots_exist),
        ("polls-closed", 10, 20, ["vote", "count"], ballots_exist),
        ("count-due", 11, 10, ["count"], ballots_exist),
    ]
    for name, day, hour, expect_fired, setup in scenarios:
        c = fresh()
        if setup is not None:
            setup(c)
        c.set_time(day, hour)
        v = c.check()
        expect(f"{name}: fires {expect_fired}", sorted(v["fired"]) == sorted(expect_fired),
               str(v["fired"]))
        # Every act the verdict offers as pending applies cleanly.
        offered = 0
        for citizen, entries in v["pending"].items():
            for entry in entries:
                # Each pending entry names its ECA and the choices available now.
                eca_id = entry["eca"] if isinstance(entry, dict) else entry
                eca = by_id.get(eca_id)
                if eca is None:
                    continue
                choices = {"selected": citizen, **entry_choices(entry)}
                try:
                    act = act_from_declaration(eca, choices)
                    offered += 1
                    c.apply(act)
                except (OracleRejected, ValueError) as e:
                    expect(f"{name}: apply {eca_id}", False, str(e))
                    break
        expect(f"{name}: {offered} pending acts all apply", offered > 0, "no acts offered")

    # Representative non-pending acts reject with a named guard.
    c = fresh()
    c.set_time(10, 20)  # polls closed at 19
    before = c.subjects()
    rejects = [
        ("vote-when-closed", {"eca": "vote", "voter": A, "candidate": B}, "polls closed"),  # hour 20
        ("nominate-when-closed", {"eca": "nominate", "citizen": A}, "registry closed"),
        ("proclaim-with-no-candidacy", {"eca": "proclaim"}, "no candidates"),
        ("announce-when-not-due", {"eca": "announce"}, "not due"),
    ]
    for name, act, fragment in rejects:
        try:
            c.apply(act)
            expect(f"{name} rejects", False, "act was accepted")
        except OracleRejected as e:
            expect(f"{name} rejects", fragment in str(e), str(e))
    expect("rejections leave the graph unchanged", c.subjects() == before, "graph changed")

    # ---- readings: a law's results without a verdict field of their own ----
    # `wouldWin` named one process's result, so a taxation or requisition law
    # had nothing to put there and any new result needed a verdict change. A
    # reading names a law-chosen id, a kind from a closed set, and a value.
    c = fresh()
    empty = c.check()["readings"]
    expect(
        "a law with no result emits no placeholder reading",
        empty == [],
        str(empty),
    )
    expect("the verdict no longer carries wouldWin", "wouldWin" not in c.check())

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

    print(f"\n{'all pass' if not fails else f'{len(fails)} FAILURES: {fails}'}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
