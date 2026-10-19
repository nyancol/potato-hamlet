"""The shared physical vocabulary, and the two checks that police its use.

Every other invariant in this repo has a test that fails when it breaks. The
vocabulary and its two report checks had none -- they were verified by hand and
then lost. This script is that test, and it exists for the same reason
`test_gate.py` does: a check that has only ever said "ok" is untested.

Three things it holds to:

  - the FILE is what the design says it is. Subset axioms only, no OWL
    restriction; capabilities are Qualities and actions are Processes; no
    inventory of instruments, because no shipped law names one.
  - the MERGE widens the vocabulary without weakening any rule. A subject
    typed by a shared class is declared; one typed by nothing is still refused.
  - the two REPORT checks fire on what they should and stay silent otherwise,
    and neither makes a set unreviewable.

Usage:
  uv run python tests/test_shared_vocabulary.py
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml
from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "lawgen"))

import check  # noqa: E402
from check import (GFO_CORE, GFO_LIGHT, PH, SHARED_VOCABULARY,  # noqa: E402
                   capability_classes, check_grounding, check_population,
                   check_tbox, declared_classes, declared_properties,
                   gfo_superclasses, parse, process_classes, subclasses_of)

fails: list[str] = []
# Scratch cases, held so their TemporaryDirectory handles stay alive: a dropped
# handle deletes the tree, and a deleted case tests nothing.
keep: list[tempfile.TemporaryDirectory] = []


def expect(name: str, cond: bool, detail: str = "") -> None:
    print(("PASS " if cond else "FAIL ") + name + (f" ({detail})" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def scratch(case: str) -> tuple[tempfile.TemporaryDirectory, Path]:
    """A throwaway copy of a case, and the handle that keeps it alive.

    The handle must not be dropped: a TemporaryDirectory deletes its tree when
    it is finalised, so `_, dest = scratch(...)` removes the case out from
    under the next line. Every caller keeps it.
    """
    tmp = tempfile.TemporaryDirectory()
    dest = Path(tmp.name) / case
    shutil.copytree(ROOT / "cases" / case, dest)
    return tmp, dest


def reports(case_dir: Path) -> dict[str, list[str]]:
    _, errors, notes = check.run(case_dir, schema_only=True)
    return {n: m for n, m in notes}, errors  # type: ignore[return-value]


def notes_of(case_dir: Path) -> dict[str, list[str]]:
    return {n: m for n, m in check.run(case_dir, schema_only=True)[2]}


def main() -> int:
    shared, errs = parse(SHARED_VOCABULARY)
    if shared is None:
        expect("the shared vocabulary parses", False, str(errs))
        return 1
    expect("the shared vocabulary parses", True)

    classes = declared_classes(shared)
    names = sorted(str(c).rsplit("/", 1)[-1] for c in classes)

    # --- the file is a frozen schema, and a legal one -------------------
    expect("no OWL restriction anywhere",
           not list(shared.triples((None, RDF.type, OWL.Restriction))),
           "an existential restriction can only require SOME qualifying object "
           "and cannot exclude one, so it would not say what it appears to say")
    expect("no individuals in the file", check_tbox(shared) == [], str(check_tbox(shared)))

    # --- named kinds may be offered, and offering one narrows no law ----
    # The gate decides "named kind" by DIRECT subclauses of the capability root,
    # so a kind sitting under a capability is invisible to the narrowing report.
    # That is the whole mechanism, and it is worth pinning: if `capability_classes`
    # ever walked transitively, every law requiring `ph:Inscriptible` would
    # silently become a law that named an instrument.
    expect("named kinds exist beneath a capability",
           all(URIRef(PH + k) in classes for k in ("Pen", "Pencil")),
           "expected ph:Pen and ph:Pencil to be declared")
    expect("a named kind sits under a capability, not the root",
           all(URIRef(PH + k) in subclasses_of(shared, URIRef(PH + "Inscriptible"))
               for k in ("Pen", "Pencil")),
           "ph:Pen and ph:Pencil must be direct subclauses of ph:Inscriptible")
    expect("a named kind is NOT itself a capability",
           not any(URIRef(PH + k) in capability_classes(shared)
                   for k in ("Pen", "Pencil")),
           "a kind read as a capability would make every law that requires "
           "ph:Inscriptible a law that named an instrument")
    expect("the capabilities are unchanged by the kinds",
           sorted(str(c).rsplit("/", 1)[-1] for c in capability_classes(shared))
           == ["Container", "Inscribable", "Inscriptible"],
           str(sorted(str(c).rsplit("/", 1)[-1]
                      for c in capability_classes(shared))))
    expect("no kind is declared without a capability above it",
           all(any(str(s).startswith(PH) for s in shared.objects(URIRef(PH + k),
                                                                RDFS.subClassOf))
               for k in ("Pen", "Pencil")),
           "a kind with no capability above it would be a law's own concept")
    expect("every property is grounded", check_grounding(shared) == [],
           str(check_grounding(shared)))
    expect("every class carries rdfs:label",
           all(list(shared.objects(c, RDFS.label)) for c in classes),
           str([str(c).rsplit("/", 1)[-1] for c in classes
                if not list(shared.objects(c, RDFS.label))]))

    # --- categories, which are the part a reader can get wrong ----------
    caps = capability_classes(shared)
    cap_names = sorted(str(c).rsplit("/", 1)[-1] for c in caps)
    quality = URIRef(GFO_LIGHT + "Quality")
    obj = URIRef(GFO_LIGHT + "Object")
    expect("a capability is a gfo-light:Quality",
           all(quality in gfo_superclasses(shared, c) for c in caps),
           "a capability is a qualification inhering in a bearer")
    expect("a capability is NOT also an Object",
           not any(obj in gfo_superclasses(shared, c) for c in caps),
           "declaring it an Object made `ph:Mailbox ⊑ ph:Container` say a "
           "mailbox IS container-ness rather than that it HAS that quality")
    expect("the capability root resolves to qualifications only",
           cap_names == ["Container", "Inscribable", "Inscriptible"], str(cap_names))

    actions = {str(c).rsplit("/", 1)[-1] for c in process_classes(shared)}
    expect("actions are gfo-core:Process",
           actions == {"PhysicalAction", "Inscribe", "Deposit"}, str(sorted(actions)))
    expect("no action is a Relator",
           not any(URIRef(GFO_LIGHT + "Relator") in gfo_superclasses(shared, c)
                   for c in classes),
           "a Relator is a truthmaker that binds relata in a state; it does not "
           "dispense ink")

    for prop in ("actedOn", "actedWith", "placedIn"):
        p = URIRef(PH + prop)
        subs = {str(s) for s in shared.objects(p, RDFS.subPropertyOf)}
        expect(f"ph:{prop} is a participation, not a relator binding",
               subs == {GFO_CORE + "hasParticipant"}, str(sorted(subs)))

    # --- offering an instrument is not the same as requiring one ---------
    # AMENDED from "no instrument class is named". The old assertion encoded
    # decision 9 as it was first written, which conflated what a law's text
    # names -- governing what a law REQUIRES -- with what the file may OFFER.
    # The vocabulary may now declare named kinds beneath a capability it already
    # declares; what it may not do is make a law require one. So the test that
    # matters is the direction: a kind may exist, and it must not read as a
    # capability, so no law is narrowed by its presence.
    law = (ROOT / "cases" / "mayor-quorum" / "law.txt").read_text().lower()
    named = re.findall(r"\b(pen|pencil|quill|chisel|marker)\w*\b", law)
    expect("the law text still names no instrument", not named,
           f"{named} -- mayor-quorum/law.txt requires a CAPABILITY, and if the "
           f"text began naming a kind the vocabulary would no longer be what the "
           f"law requires")
    for case_name in ("mayor-quorum", "mayor-2027"):
        mf = yaml.safe_load((ROOT / "cases" / case_name / "manifest.yaml").read_text())
        required = [r.get("class") for e in mf["ecas"] for r in (e.get("requires") or [])]
        expect(f"{case_name} requires the capability, not a kind",
               "Inscriptible" in required
               and not ({"Pen", "Pencil"} & set(required)),
               f"requires={required} -- a law whose text names no instrument must "
               f"not be made to require one just because the file offers it")

    # --- the merge widens the vocabulary, not the rule -------------------
    case = ROOT / "cases" / "requisitions"
    og, _ = parse(case / "ontology.ttl")
    pg, _ = parse(case / "population.ttl")
    for triple in shared:
        og.add(triple)

    probe = Graph()
    for triple in pg:
        probe.add(triple)
    probe.add((URIRef(PH + "sheet/probe"), RDF.type, URIRef(PH + "Sheet")))
    probe.add((URIRef(PH + "sheet/probe"), URIRef(PH + "label"), Literal("Scratch sheet")))
    expect("a shared-typed seed individual is declared",
           check_population(probe, og) == [], str(check_population(probe, og)))

    bad = Graph()
    for triple in pg:
        bad.add(triple)
    bad.add((URIRef(PH + "thing/probe"), RDF.type, URIRef(PH + "Sculpture")))
    bad.add((URIRef(PH + "thing/probe"), URIRef(PH + "label"), Literal("Scratch")))
    expect("an undeclared type is still refused",
           bool(check_population(bad, og)),
           "the merge must widen the vocabulary, not the rule")

    # --- the law's own classes, not the merged graph, drive the orphan
    # and reachability checks --------------------------------------------
    f = notes_of(case)
    for name in ("phase hierarchy", "orphan processes"):
        expect(f"{name} is clean on a law that uses nothing physical",
               not check.run(case, schema_only=True)[1], "")

    expect("an unused shared action is not a defect in the law",
           "phase hierarchy" not in f, "a shared Process nobody specialises "
           "into is framework vocabulary, not an unreachable phase of this law")

    _, d = scratch("mayor-quorum")
    onto = d / "ontology.ttl"
    onto.write_text(onto.read_text() + "\nph:MysteryProcess rdfs:subClassOf gfo-core:Process .\n")
    expect("a stray law-declared Process is still refused",
           "orphan processes" in dict(check.run(d, schema_only=True)[0]))

    _, d = scratch("mayor-quorum")
    onto = d / "ontology.ttl"
    onto.write_text(onto.read_text() + "\nph:MysteryVote rdfs:subClassOf ph:Deposit .\n")
    expect("a stray subclass of a shared action is still refused",
           "orphan processes" in dict(check.run(d, schema_only=True)[0]))

    _, d = scratch("mayor-quorum")
    onto = d / "ontology.ttl"
    onto.write_text(onto.read_text() + "\nph:CastVote rdfs:subClassOf ph:Deposit .\n")
    expect("a law's process specialising a shared action is accepted",
           check.run(d, schema_only=True)[1] == [],
           "the law's CastVote IS that Deposit under the law's name")

    # --- report: local redeclaration -------------------------------------
    _, d = scratch("mayor-quorum")
    onto = d / "ontology.ttl"
    onto.write_text(onto.read_text() + "\nph:Mailbox rdfs:subClassOf gfo-light:Object .\n")
    got = notes_of(d)
    expect("a restated shared class is reported",
           bool(got.get("local redeclaration")), str(got))
    expect("reporting a redeclaration does not make the set unreviewable",
           check.run(d, schema_only=True)[1] == [],
           "the reports exist so the migration is not blocked behind them")

    _, d = scratch("mayor-quorum")
    onto = d / "ontology.ttl"
    onto.write_text(onto.read_text() + "\nph:Announce ph:hasParticipant ph:Mailbox .\n")
    expect("merely REFERENCING a shared class is not a redeclaration",
           not notes_of(d).get("local redeclaration"),
           "using a concept restates nothing")

    _, d = scratch("mayor-quorum")
    onto = d / "ontology.ttl"
    onto.write_text(onto.read_text() + "\nph:Mailbox rdfs:subClassOf gfo-light:InformationObject .\n")
    msg = (notes_of(d).get("local redeclaration") or [""])[0]
    expect("the report names the disagreement when the two files differ",
           "do not even agree" in msg, msg[:120])

    # --- report: instrument narrowing ------------------------------------
    def with_requires(case_name: str, eca_id: str, cls: str) -> Path:
        tmp, dest = scratch(case_name)
        keep.append(tmp)  # the handle, so the tree outlives this call
        mf = yaml.safe_load((dest / "manifest.yaml").read_text())
        for eca in mf["ecas"]:
            if eca["id"] == eca_id:
                eca["requires"] = [{"name": "tool", "class": cls}]
        (dest / "manifest.yaml").write_text(yaml.safe_dump(mf, sort_keys=False))
        return dest

    got = notes_of(with_requires("mayor-quorum", "nominate", "ph:Sheet"))
    expect("an act qualifying by a NAMED KIND is reported",
           bool(got.get("instrument narrowing")), str(got))
    expect("the report names the ECA and the kind",
           "nominate" in (got.get("instrument narrowing") or [""])[0]
           and "Sheet" in (got.get("instrument narrowing") or [""])[0])

    got = notes_of(with_requires("mayor-quorum", "nominate", "ph:Inscriptible"))
    expect("the same act qualifying by a CAPABILITY is silent",
           not got.get("instrument narrowing"), str(got))
    got = notes_of(with_requires("mayor-quorum", "nominate", "Inscriptible"))
    expect("a bare local name resolves like a prefixed one",
           not got.get("instrument narrowing"), str(got))
    got = notes_of(with_requires("requisitions", "lodge", "ph:Container"))
    expect("the capability root is honoured, not a hardcoded list",
           not got.get("instrument narrowing"), str(got))

    # --- the shipped laws draw on it, and only what they use -------------
    for case_name in ("mayor-2027", "mayor-quorum", "requisitions"):
        d = ROOT / "cases" / case_name
        _, errors, notes = check.run(d, schema_only=True)
        expect(f"{case_name}: schema checks pass", errors == [], str(errors[:2]))
        expect(f"{case_name}: no redeclaration reported",
               not dict(notes).get("local redeclaration"), str(dict(notes)))

    print(f"\n{'all pass' if not fails else f'{len(fails)} FAILURES: {fails}'}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())