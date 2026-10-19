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
from pathlib import Path
from typing import Any

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

XSD = "http://www.w3.org/2001/XMLSchema#"
GFO_LIGHT = "https://w3id.org/gfo-light/"
GFO_CORE = "https://w3id.org/gfo-core/"
PH = "https://potato-hamlet.example/ontology/"

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


# The shared physical vocabulary, resolved alongside a case's own schema.
# Absent rather than fatal: the vocabulary is AVAILABLE to a law and required
# of none, so a client loading a law that draws on none of it works exactly as
# it did before the vocabulary existed.
SHARED_VOCABULARY = Path(__file__).resolve().parents[1] / "framework" / "physical.ttl"

# The shared populated world, resolved alongside a case's own seeds. One
# hamlet, one people, one present: every law starts in the same world and
# derives only its own calendar, instances, states and roles in its seeds.
# Absent rather than fatal, like the vocabulary: a client loading a case
# from before the world existed works exactly as it did then.
WORLD = Path(__file__).resolve().parents[1] / "framework" / "world.ttl"


def load_shared_vocabulary() -> Graph:
    """The shared physical vocabulary, or an empty graph when absent."""
    shared = Graph()
    if SHARED_VOCABULARY.exists():
        shared.parse(SHARED_VOCABULARY, format="turtle")
    return shared


def load_world() -> Graph:
    """The shared populated world, or an empty graph when absent."""
    world = Graph()
    if WORLD.exists():
        world.parse(WORLD, format="turtle")
    return world


class WorldDriftError(Exception):
    """A frozen set loaded against a world that has moved since its review."""


def world_version(target=None) -> str:
    """The world's content hash, with the clock's reading excluded.

    Identity is pinned, position is not: the runtime rewrites `ph:dayIndex`
    and `ph:atHour` on the clock with every advance, and a freeze that
    hashed the reading would invalidate itself on the first tick.
    Canonicalised over sorted triples so serialisation order cannot move it.
    This is the single definition: manifests record it, the loader checks it.
    """
    import hashlib

    from rdflib import RDF

    path = Path(target) if target is not None else WORLD
    if not path.exists():
        return "absent"
    graph = Graph()
    try:
        graph.parse(path, format="turtle")
    except Exception:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    clocks = set(graph.subjects(RDF.type, URIRef(PH + "Clock")))
    moment = {URIRef(PH + "dayIndex"), URIRef(PH + "atHour")}
    canon = "".join(
        sorted(
            f"{s.n3()} {p.n3()} {o.n3()} .\n"
            for s, p, o in graph
            if not (s in clocks and p in moment)
        )
    )
    return "sha256:" + hashlib.sha256(canon.encode()).hexdigest()


def recorded_world_version(case_dir) -> str | None:
    """The world version a case was frozen against, or None when unrecorded.

    Unreviewed sets (drafts, scratch cases) record nothing and load against
    whatever world is current: the freeze gate, not the loader, is what
    refuses the unfrozen.
    """
    import yaml

    try:
        data = yaml.safe_load((Path(case_dir) / "manifest.yaml").read_text())
    except OSError:
        return None
    return (data or {}).get("world")


def load_artefact_case(case_dir) -> tuple[Graph, Graph]:
    """Load (schema, instances) for an artefact case directory.

    The schema is the law's own declarations MERGED with the shared physical
    vocabulary, so a subject typed by a class the law drew on rather than
    declared counts as declared. Merged rather than copied into each case's
    file: the shared classes are TBox, `schema_subjects` keeps them off the
    wire, and a copy would make each frozen file look self-contained while
    its meaning depended on a copy that could drift from the original.

    The instances are the law's own seeds MERGED with the shared populated
    world, so the graph the oracle reasons about is the world the law starts
    in plus what the law derives in it. Merged for the same reason: one
    hamlet means one people, and per-case copies of Alice are what let two
    cases' worlds drift apart unnoticed.

    A case frozen against a world that has since moved is refused here, not
    just at `freeze --verify`: the recorded version names which world the
    review happened on, and running against another would silently
    reinterpret it. Cases recording nothing (drafts, scratch sets) load
    against whatever world is current.
    """
    case = Path(case_dir)
    recorded = recorded_world_version(case)
    if recorded is not None and recorded != world_version():
        raise WorldDriftError(
            f"{case} was reviewed against world {recorded}, now "
            f"{world_version()}: re-review before loading"
        )
    schema = Graph()
    schema.parse(case / "ontology.ttl", format="turtle")
    for triple in load_shared_vocabulary():
        schema.add(triple)
    instances = Graph()
    instances.parse(case / "population.ttl", format="turtle")
    for triple in load_world():
        instances.add(triple)
    return schema, instances


def dumps(payload: dict) -> str:
    """Compact, key-sorted JSON — the form the oracle receives on stdin."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)
