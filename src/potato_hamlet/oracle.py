"""Cold-spawn client for a law's compiled oracle.

The knowledge graph is the only representation of state: the client holds an
instance graph, hands it to the oracle for `check`, and adopts whatever whole
graph `apply` returns. There is no parallel state object to keep in step, so
the oracle's answer and the graph cannot drift.

`apply` replaces the stored graph wholesale rather than merging, so a
malformed response is caught before anything is committed: an undeclared
subject is an error, not a partial write.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from rdflib import Graph, Literal, URIRef

from .graphwire import dumps, graph_to_wire, load_artefact_case, wire_to_graph

PH = "https://potato-hamlet.example/ontology/"
XSD = "http://www.w3.org/2001/XMLSchema#"
RDF_TYPE = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")


class OracleRejected(Exception):
    """The oracle refused an act, naming the guard that failed."""


class UndeclaredSubject(Exception):
    """`apply` returned a subject the ontology does not declare."""


def iri(name: str) -> URIRef:
    return URIRef(PH + name)


def _int(value: int) -> Literal:
    return Literal(value, datatype=URIRef(XSD + "integer"))


class OracleClient:
    """A law's oracle plus the instance graph it operates on."""

    def __init__(self, case_dir: str | Path, timeout: int = 60):
        self.case = Path(case_dir)
        self.oracle = self.case / "oracle"
        if not self.oracle.exists():
            raise FileNotFoundError(
                f"missing oracle binary {self.oracle} (run scripts/build_oracle.py)"
            )
        self.schema, seed = load_artefact_case(self.case)
        self.declared_types = self._declared_types()
        self.graph = Graph()
        for triple in seed:
            self.graph.add(triple)
        self.timeout = timeout

    # -- schema ---------------------------------------------------------
    def _declared_types(self) -> set[str]:
        """Every class IRI the ontology declares, plus every ph: class."""
        from rdflib import RDFS

        return {
            str(o)
            for o in self.schema.objects(None, RDFS.subClassOf)
            if str(o).startswith(PH)
        } | {
            str(s) for s in self.schema.subjects(RDFS.subClassOf, None)
            if str(s).startswith(PH)
        }

    # -- graph plumbing -------------------------------------------------
    def replace(self, graph: Graph) -> None:
        """Adopt a whole graph, refusing undeclared subjects before commit."""
        for subject in graph.subjects(RDF_TYPE, None):
            if not str(subject).startswith(PH):
                continue
            declared = graph.value(subject, RDF_TYPE)
            # GFO categories are legitimate for a grounded framework (a
            # Chronoid is a gfo-light:Chronoid, not a ph: one); only the
            # ph: vocabulary is governed by this law's ontology.
            if declared is not None and str(declared).startswith(PH) \
                    and str(declared) not in self.declared_types:
                raise UndeclaredSubject(
                    f"apply returned {subject} typed by {declared}, "
                    f"which the ontology does not declare"
                )
        self.graph.remove((None, None, None))
        for triple in graph:
            self.graph.add(triple)

    def _run(self, verb: str, payload: dict | None) -> tuple[int, str, str]:
        proc = subprocess.run(
            [str(self.oracle), verb],
            input=dumps(payload) if payload is not None else None,
            capture_output=True, text=True, timeout=self.timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr

    # -- protocol -------------------------------------------------------
    def eca_ids(self) -> list[str]:
        code, out, err = self._run("list", None)
        if code != 0:
            raise RuntimeError(f"oracle list failed: {err}")
        return json.loads(out)["ecas"]

    def check(self) -> dict:
        code, out, err = self._run("check", graph_to_wire(self.graph))
        if code != 0:
            raise RuntimeError(f"oracle check failed: {err}")
        return json.loads(out)

    def apply(self, act: dict) -> dict:
        """Apply an act on behalf of a citizen; adopt the returned graph.

        Returns the verdict-less acknowledgement; raises OracleRejected with
        the named guard when the oracle refuses.
        """
        code, out, err = self._run(
            "apply", {"act": act, "graph": graph_to_wire(self.graph)["graph"]}
        )
        if code != 0:
            reason = json.loads(out).get("error") if out.strip() else err.strip()
            raise OracleRejected(reason)
        self.replace(wire_to_graph({"graph": json.loads(out)["graph"]}))
        return act

    # -- state the driver owns ------------------------------------------
    def set_clock(self, day: int, hour: int) -> None:
        """The driver's one local write: the framework-fixed clock position."""
        self.graph.set((iri("clock/now"), iri("dayIndex"), _int(day)))
        self.graph.set((iri("clock/now"), iri("atHour"), _int(hour)))

    def set_time(self, day: int, hour: int = 10, cycle_iri: str | None = None) -> None:
        """Advance time.

        The clock is always written because it is what the framework fixes. A
        law whose per-instance shape keeps the day on the cycle record (the
        history shape) also needs it there, so this writes both and stays
        law-agnostic for the caller.
        """
        self.set_clock(day, hour)
        targets = [cycle_iri] if cycle_iri else self.cycles()
        for target in targets:
            if target:
                self.graph.set((URIRef(target), iri("dayIndex"), _int(day)))
                self.graph.set((URIRef(target), iri("atHour"), _int(hour)))

    def set_cycle(self, cycle_iri: str, day: int, hour: int = 10) -> None:
        self.graph.set((URIRef(cycle_iri), iri("dayIndex"), _int(day)))
        self.graph.set((URIRef(cycle_iri), iri("atHour"), _int(hour)))

    # -- reading state back for assertions ------------------------------
    def flag(self, subject: str, name: str) -> bool:
        value = self.graph.value(URIRef(subject), iri(name))
        return value is not None and str(value) == "true"

    def cycles(self) -> list[str]:
        """Election instances, ordered by the declared ph:cycleIndex."""
        found = [
            (int(self.graph.value(s, iri("cycleIndex")) or 0), str(s))
            for s in self.graph.subjects(RDF_TYPE, iri("MayorElectionCycle"))
        ]
        return [iri_s for _, iri_s in sorted(found)]

    def current_cycle(self) -> str | None:
        ordered = self.cycles()
        return ordered[-1] if ordered else None

    def occupants(self, role_class: str, context: str | None = None) -> list[str]:
        """IRIs played by a Role instance, optionally scoped to a context."""
        out = []
        for r in self.graph.subjects(RDF_TYPE, iri(role_class)):
            if context is not None:
                target = self.graph.value(r, iri("roleIn"))
                if target is None or str(target) != context:
                    continue
            played = self.graph.value(r, iri("playedBy"))
            if played is not None:
                out.append(str(played))
        return out

    def ballots(self, cycle_iri: str | None = None) -> list[tuple[str, str]]:
        out = []
        for b in self.graph.subjects(RDF_TYPE, iri("BallotVote")):
            if cycle_iri is not None:
                tag = self.graph.value(b, iri("cycleIndex"))
                if tag is None or str(tag) != cycle_iri:
                    continue
            owner = self.occupants_of(str(b), "BallotOwnerRole")
            cand = self.occupants_of(str(b), "CandidateRole")
            if owner and cand:
                out.append((owner[0], cand[0]))
        return out

    def votes(self, cycle_iri: str | None = None) -> list[tuple[str, str]]:
        out = []
        for v in self.graph.subjects(RDF_TYPE, iri("CastVote")):
            if cycle_iri is not None:
                tag = self.graph.value(v, iri("cycleIndex"))
                if tag is None or str(tag) != cycle_iri:
                    continue
            voter = self.occupants_of(str(v), "VoterRole")
            cand = self.occupants_of(str(v), "CandidateRole")
            if voter and cand:
                out.append((voter[0], cand[0]))
        return out

    def occupants_of(self, situation: str, role_class: str) -> list[str]:
        """Citizens playing `role_class` whose roleIn is `situation`."""
        out = []
        for r in self.graph.subjects(RDF_TYPE, iri(role_class)):
            target = self.graph.value(r, iri("roleIn"))
            if target is None or str(target) != situation:
                continue
            played = self.graph.value(r, iri("playedBy"))
            if played is not None:
                out.append(str(played))
        return out

    def subjects(self) -> set[str]:
        return {str(s) for s in self.graph.subjects()}
