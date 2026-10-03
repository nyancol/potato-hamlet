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
`potato_hamlet.oracle.OracleClient`, which every consumer inherits.

Usage:
  uv run python scripts/test_client.py artefacts/mayor-2027
"""

from __future__ import annotations

import sys
from pathlib import Path

from rdflib import RDF, RDFS, Graph, URIRef

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from potato_hamlet.graphwire import graph_to_wire, wire_to_graph  # noqa: E402
from potato_hamlet.oracle import (  # noqa: E402
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


def without(graph, triple) -> "Graph":
    g = Graph()
    for t in graph:
        if t != triple:
            g.add(t)
    return g


def main(argv: list[str]) -> int:
    case = (ROOT / (argv[1] if len(argv) > 1 else "artefacts/mayor-2027")).resolve()
    print(f"graph contract — {case.name}\n")

    # ---- 3.4a: the store is replaced, not merged ------------------------
    c = OracleClient(case)
    c.set_time(0)
    c.apply({"eca": "announce"})
    stored = triples(c)
    expect(
        "an accepted act leaves the store holding what apply returned",
        stored == triples(c),
    )

    # What the oracle actually returned, straight off the wire, with nothing
    # filtered on the way through `replace`.
    code, out, _ = c._run(
        "apply", {"act": {"eca": "nominate", "citizen": CITIZEN + "alice"},
                  "graph": graph_to_wire(c.graph)["graph"]}
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
    scratch.set_time(0)
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
        g.set_time(0)
        try:
            g.apply({"eca": "announce"})
        except OracleRejected:
            pass
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

    if fails:
        print(f"\n{len(fails)} FAILURE(S): {fails}")
        return 1
    print("\nall pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
