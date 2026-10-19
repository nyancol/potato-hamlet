"""Does the review gate actually refuse what it claims to refuse?

Every gate check that only ever says "ok" is untested. This harness mutates
a real artefact set into each violation the gate is supposed to catch, runs
the gate, and requires it to fail *naming the thing that is wrong*.

It also reports, per mutation, whether the gate as it stood before the
framework-invariant work would have caught it. A mutation the old gate
missed is the point of the exercise: it is a hole that used to pass
vacuously.

A mutation whose fixture exists in only one law's shape carries `cases`
naming where it runs — Alice in the mayor seeds, lodge in the requisitions
manifest — with a sibling mutation covering the same check on the other
shape. The harness skips non-applicable mutations per case instead of
erroring on a pattern that cannot match.

Usage:
  uv run python tests/test_gate.py cases/mayor-2027

Schema-only by design: no mutation touches rule semantics, so there is no
reason to pay for a Lean typecheck 20 times.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools" / "lawgen"))
import check  # noqa: E402


def legacy_gate(case: Path) -> list[str]:
    """The gate as it stood before the framework-invariant checks.

    Reproduced from the pre-6.1 `check_ontology` and `check_manifest` so the
    comparison below is against real behaviour, not a strawman: every ph:
    class needs a GFO superclass, every ph:-typed individual needs a label,
    and the manifest needs unique ids, a declared process and a modality.
    It never opened population.ttl at all.
    """
    import yaml
    from rdflib import RDF, RDFS, Graph, URIRef

    errors: list[str] = []
    g = Graph()
    try:
        g.parse(case / "ontology.ttl")
    except Exception as e:  # noqa: BLE001
        return [f"Turtle parse failed: {e}"]
    classes = set(g.subjects(RDF.type, URIRef("http://www.w3.org/2002/07/owl#Class")))
    classes |= {s for s, _, _ in g.triples((None, RDFS.subClassOf, None))}
    for c in sorted(str(c) for c in classes):
        if not c.startswith(check.PH):
            continue
        supers = [str(o) for _, _, o in g.triples((URIRef(c), RDFS.subClassOf, None))]
        if not any(s.startswith("https://w3id.org/gfo-") for s in supers):
            errors.append(f"class <{c}> lacks a GFO-light/GFO-core superclass")
    for s in sorted(set(g.subjects(RDF.type, None))):
        s = str(s)
        if not s.startswith(check.PH):
            continue
        types = [str(o) for _, _, o in g.triples((URIRef(s), RDF.type, None))]
        if any(t.startswith(check.PH) for t in types):
            if not list(g.triples((URIRef(s), RDFS.label, None))):
                errors.append(f"individual <{s}> lacks rdfs:label")

    data = yaml.safe_load((case / "manifest.yaml").read_text())
    ecas = data.get("ecas", [])
    ids = [e.get("id") for e in ecas]
    if len(ids) != len(set(ids)):
        errors.append("duplicate eca ids")
    ph_classes = {
        str(s) for s, _, _ in g.triples((None, RDFS.subClassOf, None)) if str(s).startswith(check.PH)
    }
    for e in ecas:
        if check.PH + str(e.get("eca_process", "")) not in ph_classes:
            errors.append(f"eca '{e.get('id')}' process not a ph: class")
        if e.get("modality") not in {"should", "must", "may"}:
            errors.append(f"eca '{e.get('id')}' bad modality")
    return errors


def case_iris(case: Path) -> dict[str, str]:
    """The instance IRIs a mutation needs, read from the case itself.

    Lets a mutation be written once and applied to any law instead of
    hard-coding one case's local names. Bracketed, because that is the form
    a Turtle edit needs — an unbracketed absolute IRI is a parse error.
    """
    pop = (case / "population.ttl").read_text()
    cycle = re.search(r"<(https://potato-hamlet\.example/ontology/election/mayor-[^>]+)>", pop)
    closed = re.search(r"<(https://potato-hamlet\.example/ontology/state/pollsclosed)>", pop)
    return {
        "{cycle}": f"<{cycle.group(1)}>" if cycle else "",
        "{pollsclosed}": f"<{closed.group(1)}>" if closed else "",
    }


@dataclass
class Mutation:
    id: str
    task: str
    edits: dict[str, list[tuple[str, str]]]  # filename -> [(pattern, replacement)]
    expect_check: str
    expect_text: str
    note: str = ""
    # Most mutations only need the schema. A few cross-validate against the
    # compiled oracle, which means running it.
    needs_oracle: bool = False
    files: list[str] = field(default_factory=list)
    # Empty means every law. A mutation whose fixture exists in only one
    # law's shape (Alice in the mayor seeds, lodge in the requisitions
    # manifest) names the cases it applies to; the harness skips it
    # elsewhere instead of erroring on a pattern that cannot match.
    cases: list[str] = field(default_factory=list)

    # Filenames rooted at the case directory, except "framework/..." entries,
    # which name the shared store citizens moved to: framework/world.ttl is
    # one file every law merges, so a citizen mutation edits it in place
    # (backed up and restored by run_mutation) rather than a per-case copy.
    def paths(self, case: Path) -> dict[str, Path]:
        root = Path(__file__).resolve().parent.parent
        return {
            fname: (root / fname) if fname.startswith("framework/") else (case / fname)
            for fname in self.edits
        }

    def apply(self, case: Path) -> None:
        iris = case_iris(case)
        for fname, edits in self.edits.items():
            path = self.paths(case)[fname]
            text = path.read_text()
            for pattern, replacement in edits:
                for token, iri in iris.items():
                    replacement = replacement.replace(token, iri)
                new = re.sub(pattern, replacement, text, flags=re.M)
                if new == text:
                    raise AssertionError(
                        f"mutation {self.id}: pattern {pattern!r} matched nothing in {fname}"
                    )
                text = new
            path.write_text(text)


# Line-level drops. Each is one declaration the gate must notice is gone.
DROP = lambda p: [(p, "")]  # noqa: E731


MUTATIONS: list[Mutation] = [
    # ---- 6.1 framework invariants -------------------------------------
    Mutation(
        id="6.1-no-CalendarPoint",
        task="6.1",
        edits={"ontology.ttl": DROP(r"^ph:CalendarPoint rdfs:subClassOf.*$")},
        expect_check="framework invariants",
        expect_text="ph:CalendarPoint is not declared",
        note="the exact case the task names: previously passed vacuously",
    ),
    Mutation(
        id="6.1-no-Citizen",
        task="6.1",
        edits={"ontology.ttl": DROP(r"^ph:Citizen rdfs:subClassOf.*$")},
        expect_check="framework invariants",
        expect_text="ph:Citizen is not declared",
    ),
    Mutation(
        id="6.1-no-CalendarSpan",
        task="6.1",
        edits={"ontology.ttl": DROP(r"^ph:CalendarSpan rdfs:subClassOf.*$")},
        expect_check="framework invariants",
        expect_text="ph:CalendarSpan is not declared",
    ),
    Mutation(
        id="6.1-ungrounded-Clock",
        task="6.1",
        edits={
            "ontology.ttl": [
                (r"^ph:Clock rdfs:subClassOf gfo-light:TimeBoundary \.$", "ph:Clock rdfs:subClassOf ph:Citizen ."),
            ]
        },
        expect_check="framework invariants",
        expect_text="ph:Clock must subclass gfo-light:TimeBoundary",
        note="present but grounded on the wrong superclass",
    ),
    Mutation(
        id="6.1-ungrounded-atDate",
        task="6.1",
        edits={
            "ontology.ttl": [(r"^  rdfs:subPropertyOf gfo-core:dateTimeValue \.$", "  rdfs:subPropertyOf ph:dayIndex .")]
        },
        expect_check="framework invariants",
        expect_text="ph:atDate must be a subproperty of gfo-core:dateTimeValue",
    ),
    Mutation(
        id="6.1-no-age",
        task="6.1",
        edits={
            "ontology.ttl": [
                (
                    r"^ph:age a owl:DatatypeProperty, owl:FunctionalProperty ;$\n  rdfs:subPropertyOf gfo-core:decimalValue ;\n"
                    r"  rdfs:domain ph:Citizen ;\n  rdfs:range xsd:integer \.$",
                    "",
                )
            ]
        },
        expect_check="framework invariants",
        expect_text="ph:age is not declared",
    ),
    Mutation(
        id="6.1-no-label-property",
        task="6.1",
        edits={
            "ontology.ttl": [
                (r"^ph:label a owl:DatatypeProperty, owl:FunctionalProperty ;$\n  rdfs:subPropertyOf rdfs:label ;\n  rdfs:range xsd:string \.$", "")
            ]
        },
        expect_check="framework invariants",
        expect_text="ph:label is not declared",
    ),
    # ---- 6.3 grounding --------------------------------------------------
    Mutation(
        id="6.3-ungrounded-property",
        task="6.3",
        edits={
            "ontology.ttl": [
                ("\\Z", "\nph:supervises a owl:ObjectProperty .\n"),
            ]
        },
        expect_check="grounding",
        expect_text="ph:supervises is ungrounded",
        note="a relation invented for this law with no GFO anchor",
    ),
    Mutation(
        id="6.3-grounded-on-local-property",
        task="6.3",
        edits={
            "ontology.ttl": [
                ("\\Z", "\nph:supervises a owl:ObjectProperty ;\n  rdfs:subPropertyOf ph:relates .\n"),
            ]
        },
        expect_check="grounding",
        expect_text="ph:supervises is ungrounded",
        note="chaining onto a local property is not grounding in GFO",
    ),
    # ---- 6.2 frozen TBox and population --------------------------------
    Mutation(
        id="6.2-individual-in-ontology",
        task="6.2",
        edits={
            "ontology.ttl": [
                ("\\Z", "\n<https://potato-hamlet.example/ontology/citizen/alice> a ph:Citizen ;\n  ph:label \"Alice\" ;\n  ph:age 71 .\n"),
            ]
        },
        expect_check="frozen TBox",
        expect_text="is an individual",
        note="a citizen smuggled into the schema instead of population.ttl",
    ),
    Mutation(
        id="6.2-citizen-without-age",
        task="6.2",
        edits={
            # Citizens live in the shared world now: the edit lands there
            # (backed up and restored by the harness) and the merged graph
            # carries it into the check.
            # Rewritten to a still-valid Turtle block: dropping just the
            # age line would leave a dangling ";" and the gate would refuse
            # for a parse error rather than the reason under test.
            "framework/world.ttl": [(r"^  ph:label \"Alice\" ;$\n  ph:age 71 \.$", '  ph:label "Alice" .')]
        },
        expect_check="population",
        expect_text="citizen <https://potato-hamlet.example/ontology/citizen/alice> lacks ph:age",
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="6.2-citizen-without-age-req",
        task="6.2",
        edits={
            "framework/world.ttl": [(r"^  ph:label \"Ada\" ;$\n  ph:age 68 \.$", '  ph:label "Ada" .')]
        },
        expect_check="population",
        expect_text="citizen <https://potato-hamlet.example/ontology/citizen/ada> lacks ph:age",
        note="same check as 6.2-citizen-without-age, on a requisitions citizen",
        cases=["requisitions"],
    ),
    Mutation(
        id="6.2-citizen-without-label",
        task="6.2",
        edits={"framework/world.ttl": [(r"^  ph:label \"Bob\" ;$", "")]},
        expect_check="population",
        expect_text="citizen <https://potato-hamlet.example/ontology/citizen/bob> lacks ph:label",
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="6.2-citizen-without-label-req",
        task="6.2",
        edits={"framework/world.ttl": [(r"^  ph:label \"Barnaby\" ;$", "")]},
        expect_check="population",
        expect_text="citizen <https://potato-hamlet.example/ontology/citizen/barnaby> lacks ph:label",
        note="same check as 6.2-citizen-without-label, on a requisitions citizen",
        cases=["requisitions"],
    ),
    Mutation(
        id="6.2-undeclared-type",
        task="6.2",
        edits={
            "framework/world.ttl": [
                (r"^(\S+>) a ph:Citizen ;$", r"\1 a ph:Woodcutter ;"),
            ]
        },
        expect_check="population",
        expect_text="Woodcutter>, which ontology.ttl does not declare",
    ),
    # ---- 6.4 phase reachability ---------------------------------------
    Mutation(
        id="6.4-unreachable-DistributeBallots",
        task="6.4",
        edits={
            "ontology.ttl": [
                ("\\Z", "\nph:DistributeBallots rdfs:subClassOf gfo-core:Process .\n")
            ]
        },
        expect_check="phase hierarchy",
        expect_text="DistributeBallots> is a gfo-core:Process that no declared root reaches",
        note="the exact class the task names, reinstated to check the catch",
    ),
    # ---- 6.5 orphan processes -----------------------------------------
    Mutation(
        id="6.5-stray-container",
        task="6.5",
        edits={
            # A Process that contains a real phase but is contained by nothing
            # and named by no ECA. Reachability cannot see this: it is
            # indistinguishable from a root. The seeded individual settles it.
            "ontology.ttl": [
                (
                    "\\Z",
                    "\nph:NominationWindow rdfs:subClassOf gfo-core:Process ;\n"
                    "  ph:hasPhase ph:SelfNomination .\n",
                )
            ]
        },
        expect_check="orphan processes",
        expect_text="NominationWindow> is declared but nothing in the law reaches it",
    ),
    Mutation(
        id="6.5-nobody-produces-it",
        task="6.5",
        edits={
            "ontology.ttl": [
                ("\\Z", "\nph:Tally rdfs:subClassOf gfo-core:Process .\n")
            ]
        },
        expect_check="orphan processes",
        expect_text="Tally> is declared but nothing in the law reaches it",
    ),
    # ---- 6.6 calendar spans -------------------------------------------
    Mutation(
        id="6.6-phase-without-span",
        task="6.6",
        edits={
            # Both marksPhase lines go, reterminated: dropping the last one
            # alone would leave a dangling ";" and the gate would refuse for
            # a parse error rather than the reason under test.
            "population.ttl": [
                (
                    r"^  ph:marksPhase ph:CountVotes ;$\n  ph:marksPhase ph:ProclaimMayor \.$",
                    "  ph:marksPhase ph:CountVotes .",
                )
            ]
        },
        expect_check="calendar spans",
        expect_text="phase <https://potato-hamlet.example/ontology/ProclaimMayor> is declared but no ph:CalendarSpan",
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="6.6-phase-without-span-req",
        task="6.6",
        edits={
            # A middle line of the window's four markings: dropping it leaves
            # valid Turtle and unmarks exactly one phase.
            "population.ttl": [
                (
                    r"^  ph:marksPhase ph:ConsiderRequisition ;$\n",
                    "",
                )
            ]
        },
        expect_check="calendar spans",
        expect_text="phase <https://potato-hamlet.example/ontology/ConsiderRequisition> is declared but no ph:CalendarSpan",
        note="same check as 6.6-phase-without-span, on the requisition window",
        cases=["requisitions"],
    ),
    # ---- 6.7 no ordering between phases -------------------------------
    Mutation(
        id="6.7-phase-ordering-triple",
        task="6.7",
        edits={
            # Grounded by type so the grounding check stays quiet and the
            # ordering prohibition is the only thing left to complain.
            "ontology.ttl": [
                (
                    "\\Z",
                    "\nph:before a owl:ObjectProperty ;\n"
                    "  rdfs:domain gfo-core:Process ;\n"
                    "  rdfs:range gfo-core:Process .\n\n"
                    "ph:CastVote ph:before ph:CountVotes .\n",
                )
            ]
        },
        expect_check="phase ordering",
        expect_text="asserts <https://potato-hamlet.example/ontology/before> from",
        note="sequencing written into the schema instead of the calendar bounds",
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="6.7-phase-ordering-triple-req",
        task="6.7",
        edits={
            "ontology.ttl": [
                (
                    "\\Z",
                    "\nph:before a owl:ObjectProperty ;\n"
                    "  rdfs:domain gfo-core:Process ;\n"
                    "  rdfs:range gfo-core:Process .\n\n"
                    "ph:LodgeRequisition ph:before ph:SettleRequisition .\n",
                )
            ]
        },
        expect_check="phase ordering",
        expect_text="asserts <https://potato-hamlet.example/ontology/before> from",
        note="same check as 6.7-phase-ordering-triple, between requisition phases",
        cases=["requisitions"],
    ),
    Mutation(
        id="6.7-reversed-ordering-triple",
        task="6.7",
        edits={
            "ontology.ttl": [
                (
                    "\\Z",
                    "\nph:follows a owl:ObjectProperty ;\n"
                    "  rdfs:domain gfo-core:Process ;\n"
                    "  rdfs:range gfo-core:Process .\n\n"
                    "ph:CountVotes ph:follows ph:CastVote .\n",
                )
            ]
        },
        expect_check="phase ordering",
        expect_text="Sequencing belongs in the calendar bounds",
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="6.7-reversed-ordering-triple-req",
        task="6.7",
        edits={
            "ontology.ttl": [
                (
                    "\\Z",
                    "\nph:follows a owl:ObjectProperty ;\n"
                    "  rdfs:domain gfo-core:Process ;\n"
                    "  rdfs:range gfo-core:Process .\n\n"
                    "ph:SettleRequisition ph:follows ph:LodgeRequisition .\n",
                )
            ]
        },
        expect_check="phase ordering",
        expect_text="Sequencing belongs in the calendar bounds",
        note="same check as 6.7-reversed-ordering-triple, between requisition phases",
        cases=["requisitions"],
    ),
    # ---- 6.8 causedBy direction ---------------------------------------
    Mutation(
        id="6.8-causedBy-process-to-process",
        task="6.8",
        edits={
            "population.ttl": [("\\Z", "\n\n{cycle} ph:causedBy {cycle} .")]
        },
        expect_check="causedBy direction",
        expect_text="is not a gfo-core:State",
        note="a Process causing a Process, not a State",
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="6.8-causedBy-process-to-process-req",
        task="6.8",
        edits={
            # No requisition instance is seeded, so the mutation mints a
            # scratch one typed by the law's Process class and aims its
            # causedBy at the seed goods, which are not a State.
            "population.ttl": [
                (
                    "\\Z",
                    "\n\n<https://potato-hamlet.example/ontology/requisition/tmp> a ph:Requisition ;\n"
                    "  ph:causedBy <https://potato-hamlet.example/ontology/goods/seed> .\n",
                )
            ]
        },
        expect_check="causedBy direction",
        expect_text="is not a gfo-core:State",
        note="same check as 6.8-causedBy-process-to-process, on a scratch requisition",
        cases=["requisitions"],
    ),
    Mutation(
        id="6.8-causedBy-reversed",
        task="6.8",
        edits={
            "population.ttl": [("\\Z", "\n\n{pollsclosed} ph:causedBy {cycle} .")]
        },
        expect_check="causedBy direction",
        expect_text="is not a gfo-core:Process",
        note="the same relation read in the other direction: a State causing a Process",
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="6.8-causedBy-reversed-req",
        task="6.8",
        edits={
            "population.ttl": [
                (
                    "\\Z",
                    "\n\n<https://potato-hamlet.example/ontology/state/open> ph:causedBy ph:Requisition .\n",
                )
            ]
        },
        expect_check="causedBy direction",
        expect_text="is not a gfo-core:Process",
        note="same check as 6.8-causedBy-reversed: a requisition State causing a Process",
        cases=["requisitions"],
    ),
    # ---- 6.9 manifest cross-validation ---------------------------------
    Mutation(
        id="6.9-unknown-eca-process",
        task="6.9",
        edits={"manifest.yaml": [(r"eca_process: CountVotes", "eca_process: TallyVotes")]},
        expect_check="manifest",
        expect_text="process 'TallyVotes' is not a ph: class",
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="6.9-unknown-eca-process-req",
        task="6.9",
        edits={"manifest.yaml": [(r"^  eca_process: LodgeRequisition$", "  eca_process: TallyVotes")]},
        expect_check="manifest",
        expect_text="process 'TallyVotes' is not a ph: class",
        note="same check as 6.9-unknown-eca-process, on the lodge ECA",
        cases=["requisitions"],
    ),
    Mutation(
        id="6.9-no-holder-role",
        task="6.9",
        edits={"manifest.yaml": [(r"^  holder_role: MayorRole$", "")]},
        expect_check="manifest",
        expect_text="declares no holder_role",
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="6.9-no-holder-role-req",
        task="6.9",
        edits={
            "manifest.yaml": [
                (
                    r"^(- id: lodge\n  eca_process: LodgeRequisition\n  mints: Requisition\n)  holder_role: RequisitionerRole\n",
                    r"\1",
                )
            ]
        },
        expect_check="manifest",
        expect_text="declares no holder_role",
        note="same check as 6.9-no-holder-role, on the lodge ECA",
        cases=["requisitions"],
    ),
    Mutation(
        id="6.9-no-params",
        task="6.9",
        edits={
            # Delete the key entirely: `params: []` is a legitimate
            # declaration for an ECA that takes no parameters.
            "manifest.yaml": [
                (
                    r"^  params:\n  - name: citizen\n    role: VoterRole\n    source: selected\n",
                    "",
                )
            ]
        },
        expect_check="manifest",
        expect_text="declares no params",
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="6.9-no-params-req",
        task="6.9",
        edits={
            "manifest.yaml": [
                (
                    r"^(- id: lodge\n  eca_process: LodgeRequisition\n  mints: Requisition\n  holder_role: RequisitionerRole\n)  params:\n  - name: citizen\n    role: RequisitionerRole\n    source: selected\n",
                    r"\1",
                )
            ]
        },
        expect_check="manifest",
        expect_text="declares no params",
        note="same check as 6.9-no-params, on the lodge ECA",
        cases=["requisitions"],
    ),
    Mutation(
        id="6.9-duplicate-eca-id",
        task="6.9",
        edits={"manifest.yaml": [(r"^- id: count$", "- id: announce")]},
        expect_check="manifest",
        expect_text="duplicate eca ids",
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="6.9-duplicate-eca-id-req",
        task="6.9",
        edits={"manifest.yaml": [(r"^- id: settle$", "- id: lodge")]},
        expect_check="manifest",
        expect_text="duplicate eca ids",
        note="same check as 6.9-duplicate-eca-id, on requisition ECAs",
        cases=["requisitions"],
    ),
    # ---- 6.9 manifest vs the compiled oracle ---------------------------
    # These run the real binary, so they are not schema-only.
    Mutation(
        id="6.9-role-not-declared",
        task="6.9",
        edits={
            "manifest.yaml": [(r"^  holder_role: MayorRole$", "  holder_role: TowncrierRole")]
        },
        expect_check="manifest vs oracle",
        expect_text="holder_role names 'TowncrierRole', which ontology.ttl does not declare",
        needs_oracle=True,
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="6.9-role-not-declared-req",
        task="6.9",
        edits={
            "manifest.yaml": [
                (
                    r"^(- id: lodge\n  eca_process: LodgeRequisition\n  mints: Requisition\n  holder_role: )RequisitionerRole$",
                    r"\1TowncrierRole",
                )
            ]
        },
        expect_check="manifest vs oracle",
        expect_text="holder_role names 'TowncrierRole', which ontology.ttl does not declare",
        note="same check as 6.9-role-not-declared, on the lodge ECA",
        needs_oracle=True,
        cases=["requisitions"],
    ),
    Mutation(
        id="6.9-role-not-a-participant",
        task="6.9",
        edits={
            # A declared Role that this Process simply does not involve: the
            # manifest and the ontology can each be internally fine and still
            # disagree about who holds the duty.
            "manifest.yaml": [(r"^  holder_role: MayorRole$", "  holder_role: VoterRole")]
        },
        expect_check="manifest vs oracle",
        expect_text="does not declare a participant of",
        needs_oracle=True,
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="6.9-role-not-a-participant-req",
        task="6.9",
        edits={
            # OfficerRole is declared but LodgeRequisition involves only the
            # RequisitionerRole, so holding lodge by the officer disagrees
            # about who holds the duty.
            "manifest.yaml": [
                (
                    r"^(- id: lodge\n  eca_process: LodgeRequisition\n  mints: Requisition\n  holder_role: )RequisitionerRole$",
                    r"\1OfficerRole",
                )
            ]
        },
        expect_check="manifest vs oracle",
        expect_text="does not declare a participant of",
        note="same check as 6.9-role-not-a-participant, on the lodge ECA",
        needs_oracle=True,
        cases=["requisitions"],
    ),
    Mutation(
        id="6.9-param-role-not-declared",
        task="6.9",
        edits={
            "manifest.yaml": [(r"^    role: CandidateRole$", "    role: ScrivenerRole")]
        },
        expect_check="manifest vs oracle",
        expect_text="params[candidate] names 'ScrivenerRole', which ontology.ttl does not declare",
        needs_oracle=True,
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="6.9-param-role-not-declared-req",
        task="6.9",
        edits={
            "manifest.yaml": [(r"^    role: RequisitionerRole$", "    role: ScrivenerRole")]
        },
        expect_check="manifest vs oracle",
        expect_text="names 'ScrivenerRole', which ontology.ttl does not declare",
        note="same check as 6.9-param-role-not-declared, on requisition param roles",
        needs_oracle=True,
        cases=["requisitions"],
    ),
    Mutation(
        id="6.9-eca-not-served",
        task="6.9",
        edits={"manifest.yaml": [(r"^- id: count$", "- id: tally")]},
        expect_check="manifest vs oracle",
        expect_text="`oracle list` does not serve it",
        needs_oracle=True,
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="6.9-eca-not-served-req",
        task="6.9",
        edits={"manifest.yaml": [(r"^- id: lodge$", "- id: tally")]},
        expect_check="manifest vs oracle",
        expect_text="`oracle list` does not serve it",
        note="same check as 6.9-eca-not-served, renaming lodge to an unserved id",
        needs_oracle=True,
        cases=["requisitions"],
    ),
    # ---- 5.6 readings declared in the manifest -------------------------
    Mutation(
        id="5.6-reading-undeclared",
        task="5.6",
        edits={
            "manifest.yaml": [
                (
                    r"^- id: mayor\n  class: Citizen\n  label: Mayor\n  template:.*\n",
                    "",
                )
            ]
        },
        expect_check="readings declared",
        expect_text="emits reading 'mayor' but the readings block does not declare it",
        needs_oracle=True,
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="5.6-reading-undeclared-req",
        task="5.6",
        edits={
            "manifest.yaml": [
                (
                    r"^- id: lastSettled\n  class: Requisition\n  label: Last settled requisition\n  template:.*\n",
                    "",
                )
            ]
        },
        expect_check="readings declared",
        expect_text="emits reading 'lastSettled' but the readings block does not declare it",
        note="same check as 5.6-reading-undeclared, on the settled-requisition reading",
        needs_oracle=True,
        cases=["requisitions"],
    ),
    Mutation(
        id="5.6-no-readings-block",
        task="5.6",
        edits={
            "manifest.yaml": [
                (r"^readings:\n(?:  .*\n|    .*\n|- .*\n|  - .*\n)*", ""),
            ]
        },
        expect_check="readings declared",
        expect_text="declares no readings block",
        needs_oracle=True,
    ),
    Mutation(
        id="5.6-reading-class-undeclared",
        task="5.6",
        edits={
            "manifest.yaml": [(r"^  class: Citizen$", "  class: WoodcutterRole")]
        },
        expect_check="readings declared",
        expect_text="names class 'WoodcutterRole', which ontology.ttl does not declare",
        needs_oracle=True,
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="5.6-reading-class-undeclared-req",
        task="5.6",
        edits={
            "manifest.yaml": [(r"^  class: Requisition$", "  class: WoodcutterRole")]
        },
        expect_check="readings declared",
        expect_text="names class 'WoodcutterRole', which ontology.ttl does not declare",
        note="same check as 5.6-reading-class-undeclared, on the settled-requisition reading",
        needs_oracle=True,
        cases=["requisitions"],
    ),
    Mutation(
        id="5.6-ref-resolves-through-wrong-class",
        task="5.6",
        edits={
            # A declared class that exists but is not the one the oracle
            # resolves through: the consumer would look up the label under the
            # wrong concept.
            "manifest.yaml": [(r"^  class: Citizen$", "  class: VoterRole")]
        },
        expect_check="readings declared",
        expect_text="declares class 'VoterRole' but the oracle resolves it through",
        needs_oracle=True,
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="5.6-ref-resolves-through-wrong-class-req",
        task="5.6",
        edits={
            # RequisitionRecord is declared but the oracle resolves the
            # settled reading through the Requisition itself.
            "manifest.yaml": [(r"^  class: Requisition$", "  class: RequisitionRecord")]
        },
        expect_check="readings declared",
        expect_text="declares class 'RequisitionRecord' but the oracle resolves it through",
        note="same check as 5.6-ref-resolves-through-wrong-class, on the settled-requisition reading",
        needs_oracle=True,
        cases=["requisitions"],
    ),
    Mutation(
        id="5.6-reading-without-template",
        task="5.6",
        edits={
            # Quote-agnostic: tools/lawgen/freeze.py rewrites the manifest through
            # yaml.safe_dump, which normalises "{value} votes" to '{value} votes'.
            # A pattern pinned to one quoting style silently stops matching the
            # moment the set is frozen, and the harness reports a mutation error
            # rather than a gate failure.
            "manifest.yaml": [(r"^  template:\s+\S.*votes\S*\s*$", '  template: ""')]
        },
        expect_check="readings declared",
        expect_text="declares no template",
        needs_oracle=True,
        cases=["mayor-2027", "mayor-quorum"],
    ),
    Mutation(
        id="5.6-reading-without-template-req",
        task="5.6",
        edits={
            "manifest.yaml": [(r"^  template: '\{label\}'$", '  template: ""')]
        },
        expect_check="readings declared",
        expect_text="declares no template",
        note="same check as 5.6-reading-without-template, on the settled-requisition reading",
        needs_oracle=True,
        cases=["requisitions"],
    ),
    Mutation(
        id="6.9-eca-missing-from-manifest",
        task="6.9",
        edits={
            "manifest.yaml": [
                (
                    # nominate on the election laws, lodge on requisitions:
                    # the first citizen-driven ECA of each law.
                    r"^- id: (nominate|lodge)\n(?:  .*\n|    .*\n)*",
                    "",
                )
            ]
        },
        expect_check="manifest vs oracle",
        expect_text="`oracle list` offers eca '",
        note="the deleted ECA by id — nominate on election laws, lodge on requisitions",
        needs_oracle=True,
    ),
]


def run_mutation(case: Path, m: Mutation) -> tuple[bool, str, bool]:
    """Return (caught, message, legacy_would_catch)."""
    with tempfile.TemporaryDirectory() as tmp:
        mutated = Path(tmp) / case.name
        shutil.copytree(case, mutated)
        # Framework files are shared, not copied: back them up in place and
        # restore afterwards, so a world mutation cannot leak into the next.
        shared = {f: m.paths(case)[f].read_text() for f in m.edits if f.startswith("framework/")}
        try:
            m.apply(mutated)
            results, _, _ = check.run(mutated, schema_only=not m.needs_oracle)
        finally:
            for f, text in shared.items():
                m.paths(case)[f].write_text(text)
        errors = dict(results).get(m.expect_check) or []
        legacy = legacy_gate(mutated)
        return any(m.expect_text in e for e in errors), "\n".join(errors), not legacy


def check_exemption_is_live(case: Path) -> tuple[bool, str]:
    """The exemption list must be a real escape hatch, not dead code.

    An ungrounded property is refused; adding it to GROUNDING_EXEMPTIONS with
    a reason admits it. If the second half of that did not work, the gate
    would be unpassable rather than strict.
    """
    with tempfile.TemporaryDirectory() as tmp:
        mutated = Path(tmp) / case.name
        shutil.copytree(case, mutated)
        m = Mutation(
            id="exempt",
            task="6.3",
            edits={"ontology.ttl": [("\\Z", "\nph:supervises a owl:ObjectProperty .\n")]},
            expect_check="grounding",
            expect_text="ph:supervises is ungrounded",
        )
        m.apply(mutated)
        from rdflib import Graph

        g = Graph()
        g.parse(mutated / "ontology.ttl")
        check.GROUNDING_EXEMPTIONS["supervises"] = "test-only exemption"
        try:
            errs = check.check_grounding(g)
        finally:
            check.GROUNDING_EXEMPTIONS.clear()
        return not errs, str(errs)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    case = (Path(__file__).resolve().parent.parent / argv[1]).resolve()

    # Baseline: the unmutated set must pass, or nothing below means anything.
    _, baseline, _ = check.run(case, schema_only=False)
    if baseline:
        print(f"FAIL baseline: {case.name} does not pass the gate before mutation")
        for e in baseline:
            print(f"  {e}")
        return 1

    failures: list[str] = []
    missed_before: list[str] = []
    print(f"gate mutation harness — {case.name}\n")
    applicable = [m for m in MUTATIONS if not m.cases or case.name in m.cases]
    skipped = [m.id for m in MUTATIONS if m.cases and case.name not in m.cases]
    print(f"  {'mutation':34} {'task':5} {'gate':6} {'old gate':9}")
    print(f"  {'-' * 34} {'-' * 5} {'-' * 6} {'-' * 9}")
    for m in applicable:
        try:
            caught, message, legacy_missed = run_mutation(case, m)
        except AssertionError as e:
            failures.append(f"{m.id}: {e}")
            print(f"  {m.id:34} {m.task:5} ERROR   -")
            continue
        if not caught:
            failures.append(
                f"{m.id}: gate accepted a law that should be refused "
                f"({m.expect_check} did not report {m.expect_text!r})\n{message}"
            )
        if legacy_missed:
            missed_before.append(f"{m.id} ({m.note or m.expect_check})")
        print(
            f"  {m.id:34} {m.task:5} "
            f"{'catches' if caught else 'MISSES':6} "
            f"{'missed it' if legacy_missed else 'caught it':9}"
        )

    ok, msg = check_exemption_is_live(case)
    if not ok:
        failures.append(f"GROUNDING_EXEMPTIONS is inert: still refused {msg}")
    print(f"  {'exemption-list-is-live':34} {'6.3':5} {'ok' if ok else 'BROKEN':6}")

    print(f"\n  {len(applicable)} mutations, {len(failures)} failure(s), "
          f"{len(skipped)} skipped (fixture belongs to another law)")
    if skipped:
        for s in skipped:
            print(f"    skip {s}")
    if missed_before:
        print(
            f"  {len(missed_before)} of these passed the OLD gate vacuously — "
            f"the holes this work closes:"
        )
        for s in missed_before:
            print(f"    - {s}")
    for f in failures:
        print(f"\nFAIL {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
