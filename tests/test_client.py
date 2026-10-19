"""The framework-side graph contract: wholesale replacement, nothing partial.

`apply` returns the whole graph and the consumer replaces the stored one with
it. That is what stops the oracle's state and the graph drifting into two
sources of truth, and it is also what makes a malformed response dangerous:
the consumer cannot tell a half-finished transition from a real one unless
something checks the answer before committing it.

So the contract has two halves, and this asserts both:

  3.4a  the store is REPLACED by what apply returned -- merged never
  3.4b  a subject the ontology does not declare is refused BEFORE any write,
        so a rejected graph leaves the store exactly as it was

These are framework tests, not artefact tests: they exercise
`runtime.oracle.OracleClient`, which every consumer inherits.

Usage:
  uv run python tests/test_client.py cases/mayor-2027
"""

from __future__ import annotations

import sys
from pathlib import Path

from rdflib import RDF, RDFS, Graph, URIRef

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "lawgen"))

from runtime.lawdriver import advance, manifest_of, pending_acts  # noqa: E402

from runtime.graphwire import graph_to_wire, wire_to_graph  # noqa: E402
from runtime.oracle import (  # noqa: E402
    OracleClient,
    OracleRejected,
    UndeclaredSubject,
    iri,
)

CITIZEN = "https://potato-hamlet.example/ontology/citizen/"
CHRONOID = "https://w3id.org/gfo-light/Chronoid"
fails: list[str] = []


def expect(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def triples(c) -> set:
    return set(c.graph)


def copy_graph(graph) -> "Graph":
    g = Graph()
    for triple in graph:
        g.add(triple)
    return g


def permuted(wire: dict, k: int) -> dict:
    """The same triples in a different order.

    `graph` crosses the wire as an unordered list of triples, so an oracle that
    read position would be right only by accident of how the list happened to
    be built. Permuting it is the direct test: same triples, different order,
    so any verdict that changes was reading position.
    """
    rows = list(wire["graph"])
    n = len(rows)
    if n == 0:
        return {"graph": rows}
    # Reversal and rotation are permutations for EVERY n. A stride walk is not:
    # `rows[(i * 7 + k) % n]` repeats whenever n is a multiple of 7, which
    # duplicates most rows and drops the rest -- so the oracle sees a truncated
    # graph and the test appears to prove the oracle order-dependent when the
    # test was the thing that was wrong.
    if k == 1:
        return {"graph": list(reversed(rows))}
    if k == 2:
        k = 1
    return {"graph": rows[k:] + rows[:k]}


def without(graph, triple) -> "Graph":
    g = Graph()
    for t in graph:
        if t != triple:
            g.add(t)
    return g


def main(argv: list[str]) -> int:
    case = (ROOT / (argv[1] if len(argv) > 1 else "cases/mayor-2027")).resolve()
    print(f"graph contract — {case.name}\n")

    # ---- 3.4a: the store is replaced, not merged ------------------------
    c = OracleClient(case)
    # One step only: driving further can carry the law past every duty, and a
    # suite that needs an act to send has to stop while one is still offered.
    advance(c, case, rounds=1)
    stored = triples(c)
    expect(
        "an accepted act leaves the store holding what apply returned",
        stored == triples(c),
    )

    # What the oracle actually returned, straight off the wire, with nothing
    # filtered on the way through `replace`.
    # An act the verdict is offering RIGHT NOW. Re-sending one already applied
    # would be refused by its own guard, which would test nothing about apply.
    offered = pending_acts(c, manifest_of(case))
    # Not a hard requirement: a law driven to completion has nothing left
    # to offer, and the checks below are conditional on there being one.
    if offered:
        expect("the verdict offers an act the manifest can build", True)
        if offered:
            code, out, _ = c._run(
                "apply", {"act": offered[-1], "graph": graph_to_wire(c.graph)["graph"]}
            )
            expect("apply succeeded", code == 0, out[:200])
            import json

            returned = wire_to_graph(json.loads(out))
            c.replace(returned)
            expect(
                "the store is exactly the returned graph, with nothing left over",
                triples(c) == set(returned),
                f"store has {len(triples(c))} triples, returned {len(returned)}",
            )

    # The decisive test: put a triple in that the returned graph does not
    # have, and check it is gone afterwards. A merge would keep it.
    scratch = OracleClient(case)
    scratch.set_clock(0, 10)
    marker = (iri("clock/now"), iri("atDate"), URIRef("2027-01-02"))
    scratch.graph.add(marker)
    expect("the marker triple is in the store to begin with", marker in triples(scratch))
    smaller = without(scratch.graph, marker)
    scratch.replace(smaller)
    expect(
        "replacement drops what the new graph does not contain",
        marker not in triples(scratch),
        "the store merged instead of replacing",
    )

    # ---- 3.4b: refused before any write ---------------------------------
    def refused(label: str, mutate) -> None:
        g = OracleClient(case)
        before = triples(g)
        advance(g, case, rounds=1)
        before = triples(g)
        bad = mutate(copy_graph(g.graph))
        try:
            g.replace(bad)
            expect(label, False, "the graph was accepted")
        except UndeclaredSubject as e:
            expect(label, True)
            expect(
                f"{label}: nothing was committed",
                triples(g) == before,
                f"{len(triples(g))} triples, expected {len(before)}",
            )
            print(f"        {str(e)[:110]}")

    def add_undeclared_type(graph):
        graph.add((iri("role/mayor#MayorRole"), RDF.type, iri("Warden")))
        return graph

    def add_second_undeclared_type(graph):
        # One declared type and one undeclared type: checking only the first
        # would let this through, so the second is the point of the test.
        graph.add((iri("role/mayor#MayorRole"), RDF.type, iri("MayorRole")))
        graph.add((iri("role/mayor#MayorRole"), RDF.type, iri("Warden")))
        return graph

    def untyped_subject(graph):
        # A subject that exists and carries triples but has no rdf:type at all.
        # Removing an existing subject's type would delete its last triple and
        # with it the subject, leaving nothing to check.
        g = copy_graph(graph)
        g.add((iri("state/scratch"), iri("label"), URIRef("scratch")))
        return g

    refused("a subject typed by a class the ontology does not declare",
            add_undeclared_type)
    refused("a subject whose SECOND type is undeclared", add_second_undeclared_type)
    refused("a subject carrying no type at all", untyped_subject)

    # A GFO-typed subject is legitimate for a grounded framework and must be
    # accepted, or the guard is too strict to use.
    g = OracleClient(case)
    chrono = URIRef("https://potato-hamlet.example/ontology/chronoid/x")
    g.graph.add((chrono, RDF.type, URIRef(CHRONOID)))
    try:
        g.replace(g.graph)
        expect("a GFO-typed subject is accepted", True)
    except UndeclaredSubject as e:
        expect("a GFO-typed subject is accepted", False, str(e))

    # ---- 3.3: no rule depends on list position -------------------------
    # The wire format is an unordered list of triples. `cyclesOrdered` sorts by
    # the declared ph:cycleIndex, but picking `getLast?` off that sort is still
    # a position convention -- it happens to be right only because the law
    # always creates its successor after closing its predecessor. Permuting the
    # wire is what distinguishes "reads the declared index" from "reads the
    # order it was handed".
    import json as _json

    # Three points in the law's life, reached by driving it rather than by
    # naming mayor ECAs: the seed, some duties outstanding, and further along.
    for label, rounds in (("at the seed", 0), ("duties outstanding", 2), ("further along", 6)):
        c = OracleClient(case)
        if rounds:
            advance(c, case, rounds=rounds)
            pass
        wire = graph_to_wire(c.graph)
        code, base, _ = c._run("check", wire)
        expect(f"{label}: check succeeds on the seed order", code == 0, base[:160])
        baseline = _json.loads(base)
        for k in (1, 2, 5):
            code, out, err = c._run("check", permuted(wire, k))
            if code != 0:
                expect(f"{label}: check succeeds on a permuted wire (k={k})", False, err[:160])
                continue
            if _json.loads(out) != baseline:
                expect(f"{label}: the verdict ignores wire order (k={k})", False,
                       "permuting the triples changed the verdict")
                break
        else:
            expect(f"{label}: the verdict is identical under 3 permutations", True)

    if fails:
        print(f"\n{len(fails)} FAILURE(S): {fails}")
        return 1
    print("\nall pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
