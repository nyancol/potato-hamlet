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

from .graphwire import WorldDriftError, dumps, graph_to_wire, load_artefact_case, wire_to_graph

PH = "https://potato-hamlet.example/ontology/"
XSD = "http://www.w3.org/2001/XMLSchema#"
GFO = ("https://w3id.org/gfo-light/", "https://w3id.org/gfo-core/")
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
                f"missing oracle binary {self.oracle} (run tools/lawgen/build_oracle.py)"
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
        """Adopt a whole graph, refusing anything undeclared before commit.

        The store is replaced rather than merged, so this is the only place a
        returned graph is inspected. Validation runs to completion BEFORE a
        single triple is written: a partial write is exactly what wholesale
        replacement exists to prevent, and a graph the oracle half-returned
        would leave the consumer believing a transition that never finished.

        A subject is acceptable when it carries at least one rdf:type, and
        every ph: type among them is one this ontology declares. GFO
        categories are legitimate for a grounded framework -- a Chronoid is a
        gfo-light:Chronoid, not a ph: one -- so only the ph: vocabulary is
        governed here.
        """
        for subject in sorted({s for s in graph.subjects() if isinstance(s, URIRef)}):
            if not str(subject).startswith(PH):
                continue
            types = [o for o in graph.objects(subject, RDF_TYPE) if isinstance(o, URIRef)]
            if not types:
                raise UndeclaredSubject(
                    f"apply returned {subject} carrying no rdf:type, so a consumer "
                    f"cannot tell what it is"
                )
            for declared in types:
                if str(declared).startswith(PH) and str(declared) not in self.declared_types:
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
        """The runtime's one local write: the framework-fixed clock position.

        The only way to advance time. `set_time` and `set_cycle` used to sit
        beside this and also write `ph:dayIndex` / `ph:atHour` onto process
        instances, because a law that kept the day on its own cycle record needed
        it there -- "stays law-agnostic for the caller", at the cost of asking
        every caller to know how many places a given law kept its now. No law
        does: `ph:dayIndex` is declared on `gfo-light:TimeBoundary`, so a process
        instance carries no position and the clock is the whole of it.
        """
        self.graph.set((iri("clock/now"), iri("dayIndex"), _int(day)))
        self.graph.set((iri("clock/now"), iri("atHour"), _int(hour)))

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

    def _occupant(self, situation: str, role_class: str) -> str | None:
        """The holder of `role_class` whose `roleIn` is `situation`."""
        for r in self.graph.subjects(RDF_TYPE, iri(role_class)):
            if str(self.graph.value(r, iri("roleIn")) or "") == situation:
                played = self.graph.value(r, iri("playedBy"))
                if played is not None:
                    return str(played)
        return None

    def ballot_records(self, cycle_iri: str | None = None) -> list[dict]:
        """Every ballot of a cycle as the graph states it.

        Two mayor flavours ship and they record a ballot differently, so both are
        read. `mayor-quorum` makes the ballot a MEANING a sheet plays:
        `ph:BallotVote` is a `gfo-light:Role`, the sheet is its single holder,
        the candidate comes from `ph:denotes` -- never from comparing the marking
        on the paper to a citizen's name -- the owner is the sheet's `ph:ownedBy`,
        and the mailbox is `ph:deliveredTo` on the Role.

        `mayor-2027` predates that rewrite and types the ballot itself, reading
        owner and candidate off two `ph:playedBy` values. It has no sheet, so
        `sheet`, `mailbox` and `marked` are `None` for it.

        `mailbox` is per ballot and not per sheet on purpose. One supply of paper
        serves every election, so a sheet left in a mailbox by one election is
        still there for the next; recording delivery on the sheet would make the
        next election's ballots read as delivered before anyone carried them.
        """
        out = []
        for b in self.graph.subjects(RDF_TYPE, iri("BallotVote")):
            if cycle_iri is not None:
                tag = self.graph.value(b, iri("cycleIndex"))
                if tag is None or str(tag) != cycle_iri:
                    continue
            sheet = self.graph.value(b, iri("playedBy"))
            cand = self.graph.value(b, iri("denotes"))
            marked = self.written_on(str(sheet)) if sheet is not None else None
            if sheet is not None and cand is not None:
                owner = self.graph.value(sheet, iri("ownedBy"))
                if owner is None:
                    continue
                mailbox = self.graph.value(b, iri("deliveredTo"))
                out.append({
                    "role": str(b), "sheet": str(sheet), "owner": str(owner),
                    "candidate": str(cand),
                    "mailbox": str(mailbox) if mailbox is not None else None,
                    "marked": marked,
                })
            else:
                # The older shape: owner and candidate are two Roles played by the
                # ballot itself, each its own individual so neither is ambiguous.
                owner = self._occupant(str(b), "BallotOwnerRole")
                cand = self._occupant(str(b), "CandidateRole")
                if owner is None or cand is None:
                    continue
                out.append({
                    "role": str(b), "sheet": None, "owner": owner,
                    "candidate": cand, "mailbox": None, "marked": None,
                })
        return out

    def ballots(self, cycle_iri: str | None = None) -> list[tuple[str, str]]:
        """(owner, candidate) for each ballot of a cycle."""
        return [(r["owner"], r["candidate"]) for r in self.ballot_records(cycle_iri)]

    def ballot_sheets(self, cycle_iri: str | None = None) -> list[tuple[str, str, str]]:
        """(sheet, owner, candidate) for each ballot -- the sheet is the holder."""
        return [(r["sheet"], r["owner"], r["candidate"])
                for r in self.ballot_records(cycle_iri)]

    def written_on(self, sheet: str) -> str | None:
        """The marking currently on a sheet -- its own `ph:label`.

        This is the paper's present state, not its history: a sheet reused by a
        later election is struck and rewritten, and holds one marking at a time.
        """
        label = self.graph.value(URIRef(sheet), iri("label"))
        return str(label) if label is not None else None

    def mailbox_of(self, citizen: str) -> str | None:
        """The mailbox the seed gives a citizen -- law.txt:12, "the mailbox of
        each citizen". `deliver` must reach this one and no other."""
        for m in self.graph.subjects(RDF_TYPE, iri("Mailbox")):
            owner = self.graph.value(m, iri("ownedBy"))
            if owner is not None and str(owner) == citizen:
                return str(m)
        return None

    def written_on(self, sheet: str) -> str | None:
        """The text written on a sheet -- its own label, the mark on the paper."""
        label = self.graph.value(URIRef(sheet), iri("label"))
        return str(label) if label is not None else None

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
