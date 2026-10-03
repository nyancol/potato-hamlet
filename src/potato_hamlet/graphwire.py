"""Instance-triple wire format shared by the oracle's `check` and `apply`.

The knowledge graph *is* the snapshot. It crosses the oracle boundary as a
flat JSON array of triples carrying only the ABox — typed individuals and
their property values — never the TBox (subClassOf, subPropertyOf, domain,
range, type declarations), which stays frozen in `ontology.ttl`.

Shape
-----
    {"graph": [
        ["<subject-iri>", "<predicate-iri>", "<object-iri>"],
        ["<subject-iri>", "<predicate-iri>",
         {"lit": "71", "type": "integer"}]
    ]}

An IRI object is a bare JSON string; a literal object is a tagged JSON object
carrying its lexical form and a short datatype name. IRIs are always written
in full: no prefix table is transmitted, so there is nothing to resolve and
nothing to get out of step.

Datatype short names map to XSD as in `XSD_BY_SHORT`; an unrecognised
datatype round-trips as its full IRI under the "iri" short name, so no data
is lost to an unknown type.
"""

from __future__ import annotations

import json
from typing import Any

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

XSD = "http://www.w3.org/2001/XMLSchema#"
GFO_LIGHT = "https://w3id.org/gfo-light/"
GFO_CORE = "https://w3id.org/gfo-core/"

XSD_BY_SHORT = {
    "integer": XSD + "integer",
    "string": XSD + "string",
    "date": XSD + "date",
    "boolean": XSD + "boolean",
}
SHORT_BY_XSD = {v: k for k, v in XSD_BY_SHORT.items()}

# A triple belongs to the ABox — the world the oracle reasons about — when
# its subject is an individual. A triple whose subject is a schema-declared
# class or property belongs to the TBox and never crosses the boundary.
#
# Classifying by subject rather than by predicate is what makes this robust:
# a property declaration is `ph:age rdf:type owl:DatatypeProperty`, whose
# predicate is plain rdf:type, so any predicate-pattern rule leaks it.
SCHEMA_TYPE_PREDICATES = (
    OWL.Class, OWL.DatatypeProperty, OWL.ObjectProperty,
    OWL.AnnotationProperty, OWL.NamedIndividual,
)


def schema_subjects(graph: Graph) -> set:
    """Subjects this graph declares as classes or properties (the TBox)."""
    subjects: set = set()
    for s in graph.subjects(RDFS.subClassOf, None):
        subjects.add(s)
    for s in graph.subjects(RDFS.subPropertyOf, None):
        subjects.add(s)
    for pred in SCHEMA_TYPE_PREDICATES:
        for s in graph.subjects(RDF.type, pred):
            subjects.add(s)
    return subjects


def _lit_to_json(lit: Literal) -> dict[str, str]:
    dt = str(lit.datatype) if lit.datatype else XSD + "string"
    return {"lit": str(lit), "type": SHORT_BY_XSD.get(dt, "iri")}


def _obj_to_json(obj: Any) -> Any:
    if isinstance(obj, URIRef):
        return str(obj)
    if isinstance(obj, Literal):
        return _lit_to_json(obj)
    if isinstance(obj, BNode):
        # Blank nodes have no stable identity across a round trip; the
        # contract uses full IRIs for everything the oracle reasons about.
        raise ValueError(f"blank node is not representable on the wire: {obj}")
    raise TypeError(f"unsupported RDF term: {obj!r}")


def graph_to_wire(graph: Graph) -> dict[str, list]:
    """Serialise the ABox of `graph` to the wire format.

    `graph` is the full artefact graph (schema + instances); only triples
    whose subject is an individual are sent. Triple order is normalised so
    the same graph always produces the same bytes, which keeps oracle output
    diffable.
    """
    schema = schema_subjects(graph)
    rows: list[list[Any]] = []
    for s, p, o in graph:
        if s in schema:
            continue
        if not isinstance(s, URIRef):
            raise ValueError(f"subject must be an IRI, got {s!r}")
        rows.append([str(s), str(p), _obj_to_json(o)])
    rows.sort(key=lambda r: (r[0], r[1], json.dumps(r[2], sort_keys=True)))
    return {"graph": rows}


def wire_to_graph(payload: dict) -> Graph:
    """Parse the wire format back into an rdflib Graph."""
    if "graph" not in payload:
        raise ValueError('wire payload has no "graph" key')
    graph = Graph()
    for row in payload["graph"]:
        if not isinstance(row, list) or len(row) != 3:
            raise ValueError(f"triple must be a 3-element array: {row!r}")
        subj, pred, obj = row
        s, p = URIRef(subj), URIRef(pred)
        if isinstance(obj, str):
            graph.add((s, p, URIRef(obj)))
        elif isinstance(obj, dict) and "lit" in obj:
            short = obj.get("type", "string")
            graph.add((s, p, Literal(obj["lit"], datatype=XSD_BY_SHORT.get(short, short))))
        else:
            raise ValueError(f"object must be an IRI string or a literal object: {obj!r}")
    return graph


def _norm(triple: tuple[Any, Any, Any]) -> tuple[str, str, Any]:
    """Comparable form of a triple, applying RDF 1.1 literal equivalence.

    A literal with no datatype and one typed xsd:string denote the same
    value, so they normalise alike; Turtle writes the first and JSON always
    writes the second, and treating them as different would report a loss
    that has not happened.
    """
    s, p, o = triple
    if isinstance(o, Literal):
        dt = str(o.datatype) if o.datatype else XSD + "string"
        return (str(s), str(p), (str(o), SHORT_BY_XSD.get(dt, dt)))
    return (str(s), str(p), str(o) if isinstance(o, URIRef) else str(o))


def round_trip(graph: Graph) -> Graph:
    """Serialise and re-parse, asserting no triple is lost or altered."""
    schema = schema_subjects(graph)
    before = {_norm(t) for t in graph if t[0] not in schema}
    after = {_norm(t) for t in wire_to_graph(graph_to_wire(graph))}
    if before != after:
        lost = before - after
        gained = after - before
        raise AssertionError(
            f"graph round trip lost {len(lost)} triple(s) and gained {len(gained)}"
            + (f"; lost sample: {sorted(map(str, lost))[:3]}" if lost else "")
            + (f"; gained sample: {sorted(map(str, gained))[:3]}" if gained else "")
        )
    return wire_to_graph(graph_to_wire(graph))


def load_artefact_case(case_dir) -> tuple[Graph, Graph]:
    """Load (schema, instances) for an artefact case directory."""
    from pathlib import Path

    case = Path(case_dir)
    schema = Graph()
    schema.parse(case / "ontology.ttl", format="turtle")
    instances = Graph()
    instances.parse(case / "population.ttl", format="turtle")
    return schema, instances


def dumps(payload: dict) -> str:
    """Compact, key-sorted JSON — the form the oracle receives on stdin."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)
