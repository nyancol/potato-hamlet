"""Machine checks for a law artefact set: the review gate.

Usage:
  uv run python tools/lawgen/check.py cases/mayor-2027
  uv run python tools/lawgen/check.py --schema-only cases/mayor-2027

The gate is what stands between a law and being freezable, so every check
here is a *refusal*: it names the offending declaration and stops. There are
no warnings.

Schema checks (fast, no Lean):
  1. ontology.ttl and population.ttl parse as Turtle (rdflib).
  2. framework invariants: the classes and properties without which a
     law-agnostic consumer cannot operate, each GFO-grounded.
  3. grounding: every declared property is grounded in GFO (or RDFS) by
     subproperty, or by a GFO domain/range pair.
  4. the ontology is a frozen TBox: it declares no individuals, and every
     class it declares has a GFO-light/GFO-core superclass.
  5. population.ttl: every subject is typed, every citizen carries label
     and age.
  6. manifest.yaml parses; eca ids unique; each eca_process is a ph: class.

Lean check (slow):
  7. rules.lean typechecks via `lake env lean <file>`.

Runtime checks (need a compiled oracle; see tests/test_oracle.py):
  clock totality, graph round trip.

On failure the harness reports diagnostics and marks the set unreviewable
until regenerated or fixed (spec: Machine checks before human review).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# The shared physical vocabulary: a framework artefact, not part of any
# case, so a concept a law's text presupposes is declared once and every
# law referring to it refers to the same class. Resolved alongside each
# case's ontology.ttl rather than copied into it -- a copy would make each
# law's frozen file look self-contained while its meaning depended on a
# copy that could drift from this one.
SHARED_VOCABULARY = ROOT / "framework" / "physical.ttl"

# The shared populated world: one hamlet, one people, one present. Merged
# with each case's law seeds so every population check judges the graph the
# simulation actually runs: the world the law starts in plus what the law
# derives in it.
WORLD = ROOT / "framework" / "world.ttl"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runtime.lawdriver import (act_from_declaration, apply_declared, calendar_moments,
                       drive_to_pending, manifest_of, pending_acts,
                       play_forward)  # noqa: E402

sys.path.insert(0, str(ROOT))
from runtime.graphwire import graph_to_wire, wire_to_graph  # noqa: E402

import yaml
from rdflib import OWL, RDF, RDFS, Graph, Namespace, URIRef

PH = "https://potato-hamlet.example/ontology/"
GFO_LIGHT = "https://w3id.org/gfo-light/"
GFO_CORE = "https://w3id.org/gfo-core/"

PREFIXES = {
    "ph": PH,
    "gfo-light": GFO_LIGHT,
    "gfo-core": GFO_CORE,
    "rdfs": str(RDFS),
    "rdf": str(RDF),
    "owl": str(OWL),
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}
# Vocabularies the gate accepts as a grounding target or a class source
# without the law having to restate them. GFO is the imported upper
# ontology; RDFS/OWL/XSD carry no law semantics.
IMPORTED = (GFO_LIGHT, GFO_CORE, str(RDFS), str(RDF), str(OWL), PREFIXES["xsd"])
# Properties the framework and the shipped laws write with an APPEND rather than
# a set, because a subject may legitimately hold several. Listed so the
# functional-declaration check can exempt them by name instead of demanding a
# declaration the law deliberately withholds.
SET_VALUED_BY_DESIGN = {
    "ph:marksPhase",    # one moment may mark several phases
    "ph:hasParticipant",  # a situation has many participants
    "ph:playedBy",      # a role class is played by one, a ballot by many
    "ph:roleIn",        # a role is played in several contexts
    "ph:relates",       # a relator relates many things
    "ph:containsRole",
}
# Seed properties the seed-parity check must not delete. These are what MAKES an
# individual legible rather than a value a condition might read: a type says
# what a thing is, a label how to show it, and a bound which moments it spans.
# Removing one does not test duplication -- it breaks the graph -- and their
# presence is `check_population`'s business, not this one's.
STRUCTURAL_PROPERTIES = {PH + "label"}
# Properties a law declares for a CONSUMER rather than for a condition, so their
# appearing nowhere in rules.lean is correct and not duplication.
#
# The distinction is the framework's own vocabulary against the law's, which is
# already declarative: FRAMEWORK_PROPERTIES and FRAMEWORK_LABEL are the floor
# every law must declare, and each is mandated for a reader's sake -- ph:label
# so an individual can be shown, ph:atDate so a date can be displayed without
# computing one, ph:age as a framework-required citizen attribute. Grounding
# does NOT distinguish them: ph:atDate and ph:announceDay are grounded
# identically, so a rule read off the grounding would exempt the very values it
# should report. The framework requiring a property is the reason it may go
# unread; a law inventing one and never reading it is duplication.
#
# CLASS_LEVEL_ONLY are relations a law declares for a reader instead: ph:causedBy
# states a permitted dependency only the Lean guard evaluates, and ph:hasPhase /
# ph:marksPhase describe structure a consumer walks.
CLASS_LEVEL_ONLY = {"causedBy", "hasPhase", "marksPhase", "relates", "qualityOf"}
# Classes a law declares as the PHASES of its processes. An act bringing one
# into existence is an occurrence or a process instance, both legitimately new;
# only a class outside this set that an act conjures is a physical thing the law
# should have found already there. Derived from the ontology's declared
# hierarchy rather than listed, so a law's own phases need no exemption here.
PHASE_CLASSES: set[str] = set()


def expand(term: str) -> URIRef:
    """Resolve a prefixed name like `ph:Citizen` to an absolute IRI."""
    prefix, _, local = term.partition(":")
    if prefix not in PREFIXES:
        raise ValueError(f"unknown prefix in {term!r}")
    return URIRef(PREFIXES[prefix] + local)



# --------------------------------------------------------------------------
# Framework invariants.
#
# A law may invent any vocabulary it likes for its own domain, but these it
# cannot omit: they are the only things a law-agnostic consumer is entitled
# to assume. Spec: "Every law SHALL additionally declare the
# framework-invariant classes without which a law-agnostic consumer cannot
# operate". Each entry names the grounding it must carry, so an ungrounded
# invariant fails exactly as a missing one does.
# --------------------------------------------------------------------------
FRAMEWORK_CLASSES: dict[str, str] = {
    "Citizen": "gfo-light:Object",
    "Clock": "gfo-light:TimeBoundary",
    "CalendarPoint": "gfo-light:TimeBoundary",
    "CalendarSpan": "gfo-light:Chronoid",
}

FRAMEWORK_PROPERTIES: dict[str, str] = {
    "atDate": "gfo-core:dateTimeValue",
    "age": "gfo-core:decimalValue",
    "atHour": "gfo-core:decimalValue",
    "dayIndex": "gfo-core:decimalValue",
}

# ph:label is the framework's own: spec requires it on both seeded and
# minted individuals, over rdfs:label rather than rdfs:label directly.
FRAMEWORK_LABEL = "ph:label"

# The framework's own vocabulary, derived rather than restated: these are the
# properties every law MUST declare, so the framework requiring one is the
# reason it may go unread by a condition. A law inventing its own and never
# reading it is a second source, and that is the difference this draws.
FRAMEWORK_OWN_VOCABULARY = set(FRAMEWORK_PROPERTIES) | {"label"}

# --------------------------------------------------------------------------
# Grounding exemptions.
#
# Published rather than inferred: a property grounded by neither
# rdfs:subPropertyOf nor a GFO domain/range pair fails the gate, and the only
# way past it is to appear here with a written reason. Empty is the correct
# state — every property both laws declare is grounded, `ph:marksPhase` by
# type because its object is a Process CLASS (see the comment in
# ontology.ttl) rather than an instance.
# --------------------------------------------------------------------------
GROUNDING_EXEMPTIONS: dict[str, str] = {}

# --------------------------------------------------------------------------
# Structural vocabulary.
# --------------------------------------------------------------------------

# Property relating a Process class to its constituent phases.
HAS_PHASE = expand("ph:hasPhase")
# Property relating a calendar node to the Process phase it bounds.
MARKS_PHASE = expand("ph:marksPhase")
# Property naming the Roles a Process class involves.
HAS_PARTICIPANT = expand("ph:hasParticipant")
# Property stating a permitted causal dependency: Process -> State.
CAUSED_BY = expand("ph:causedBy")

PROCESS = expand("gfo-core:Process")
STATE = expand("gfo-core:State")
CHRONOID = expand("gfo-light:Chronoid")
# A declared ECA with no complete act buildable here. Distinct from a
# refusal, and from acceptance: "not offered" is a fact about the
# verdict, and comparing against it is what makes the monotonicity
# comparison total over the law's declared acts.
NOT_OFFERED = "\x00not offered"
TIME_BOUNDARY = expand("gfo-light:TimeBoundary")
CALENDAR_POINT = expand("ph:CalendarPoint")
CALENDAR_SPAN = expand("ph:CalendarSpan")

# Local names that express sequencing. Sequencing between phases belongs in
# the calendar bounds, never in the schema: a phase-to-phase ordering triple
# in the TBox duplicates the schedule and cannot be checked against it.
ORDERING_PROPS = frozenset(
    {
        "before", "after", "precedes", "follows", "prior", "next",
        "then", "first", "last", "sequence", "step", "ordering", "order",
    }
)


def parse(path: Path) -> tuple[Graph | None, list[str]]:
    g = Graph()
    try:
        g.parse(path)
    except Exception as e:  # noqa: BLE001 - diagnostics surface verbatim
        return None, [f"{path.name}: Turtle parse failed: {e}"]
    return g, []


def parse_shared() -> tuple[Graph | None, list[str]]:
    """The shared physical vocabulary, or None when it is absent.

    Absent rather than fatal, because the vocabulary is AVAILABLE to a law
    and required of none. A run with no shared file is a run of the
    framework as it was before the vocabulary existed, and every check
    below behaves exactly as it did then rather than failing on a file no
    law asked for.
    """
    path = SHARED_VOCABULARY
    if not path.exists():
        return None, []
    return parse(path)


def parse_world() -> tuple[Graph | None, list[str]]:
    """The shared populated world, or None when it is absent.

    Absent rather than fatal, for the same reason as the shared vocabulary:
    a run with no world file behaves exactly as it did before the world
    existed. Every shipped case is expected to have one.
    """
    if not WORLD.exists():
        return None, []
    return parse(WORLD)


def declared_classes(g: Graph) -> set[URIRef]:
    """Subjects that appear as class declarations."""
    return {s for s in g.subjects(RDFS.subClassOf, None)} | set(
        g.subjects(RDF.type, OWL.Class)
    )


def declared_properties(g: Graph) -> set[URIRef]:
    return set(g.subjects(RDF.type, OWL.ObjectProperty)) | set(
        g.subjects(RDF.type, OWL.DatatypeProperty)
    )


def values_of(g: Graph, subj: URIRef, pred: URIRef) -> set[URIRef]:
    return {o for o in g.objects(subj, pred) if isinstance(o, URIRef)}


def check_framework_invariants(g: Graph) -> list[str]:
    """The framework's floor: declared, and GFO-grounded (spec 6.1)."""
    errors: list[str] = []
    classes = declared_classes(g)

    for name, superclass in FRAMEWORK_CLASSES.items():
        cls = expand(f"ph:{name}")
        if cls not in classes:
            errors.append(
                f"framework invariant: ph:{name} is not declared. A law-agnostic "
                f"consumer assumes it exists; declare it as a subclass of {superclass}."
            )
            continue
        supers = values_of(g, cls, RDFS.subClassOf)
        want = expand(superclass)
        if want not in supers:
            have = ", ".join(sorted(str(s) for s in supers)) or "nothing"
            errors.append(
                f"framework invariant: ph:{name} must subclass {superclass}, "
                f"but declares {have}"
            )

    props = declared_properties(g)
    for name, superprop in FRAMEWORK_PROPERTIES.items():
        prop = expand(f"ph:{name}")
        if prop not in props:
            errors.append(
                f"framework invariant: ph:{name} is not declared as a property; "
                f"declare it as a subproperty of {superprop}."
            )
            continue
        want = expand(superprop)
        subs = values_of(g, prop, RDFS.subPropertyOf)
        if want not in subs:
            have = ", ".join(sorted(str(s) for s in subs)) or "nothing"
            errors.append(
                f"framework invariant: ph:{name} must be a subproperty of "
                f"{superprop}, but declares {have}"
            )

    label = expand(FRAMEWORK_LABEL)
    if label not in props:
        errors.append(
            f"framework invariant: {FRAMEWORK_LABEL} is not declared. Seeded and "
            f"minted individuals carry their label through it; declare it as a "
            f"subproperty of rdfs:label."
        )
    elif RDFS.label not in values_of(g, label, RDFS.subPropertyOf):
        errors.append(
            f"framework invariant: {FRAMEWORK_LABEL} must be a subproperty of rdfs:label"
        )

    return errors


def check_grounding(g: Graph) -> list[str]:
    """Every declared property grounded in GFO (or RDFS) (spec 6.3)."""
    errors: list[str] = []
    for prop in sorted(declared_properties(g), key=str):
        name = str(prop)
        if not name.startswith(PH):
            continue
        short = name[len(PH) :]
        if short in GROUNDING_EXEMPTIONS:
            continue
        subprops = values_of(g, prop, RDFS.subPropertyOf)
        if any(str(s).startswith(IMPORTED) for s in subprops):
            continue
        # Grounding by type: both ends declared against a GFO category.
        doms = values_of(g, prop, RDFS.domain)
        rngs = values_of(g, prop, RDFS.range)
        if doms and rngs and all(
            str(d).startswith(IMPORTED) for d in doms
        ) and all(str(r).startswith(IMPORTED) for r in rngs):
            continue
        if not subprops and not doms:
            detail = "it declares no rdfs:subPropertyOf and no domain/range"
        elif not subprops:
            detail = "it declares no rdfs:subPropertyOf"
        else:
            detail = (
                "its only subPropertyOf target is "
                + ", ".join(sorted(str(s) for s in subprops))
                + ", which is not an imported relation"
            )
        errors.append(
            f"grounding: ph:{short} is ungrounded — {detail}. Ground it by "
            f"rdfs:subPropertyOf a GFO relation it coincides with, or by "
            f"declaring GFO classes as its domain and range. If it genuinely "
            f"cannot be, list it in GROUNDING_EXEMPTIONS with a reason."
        )
    return errors


def functional_properties(g: Graph) -> set[URIRef]:
    """Every property declared `owl:FunctionalProperty`."""
    return {p for p in declared_properties(g)
            if OWL.FunctionalProperty in g.objects(p, RDF.type)}


def check_reencoded_are_functional(g: Graph, reencoded: set[str]) -> list[str]:
    """A REPEATEDLY rewritten property must be declared single-valued.

    Not every written property: one written once is indistinguishable from one
    appended every act, so "written" cannot be read as "single-valued". What IS
    observable is that the oracle rewrites these properties at all -- so they
    are reported unless the law declares them functional or lists them as
    deliberately set-valued. A law whose oracle appends where it should set is
    otherwise indistinguishable from one that sets correctly, and a bound or a
    flag could be read as whichever value was written last.

    The limit is worth stating: this cannot catch a property that is appended
    and happens to carry one value in every reachable state. Only
    `check_no_accumulation` sees that, and only once a second value exists.
    """
    errors: list[str] = []
    declared = functional_properties(g)
    for name in sorted(reencoded - SET_VALUED_BY_DESIGN):
        prop = expand(name)
        if prop not in declared_properties(g):
            continue  # not this law's vocabulary; nothing to declare
        if prop not in declared:
            errors.append(
                f"functional: {name} is rewritten by the oracle but ontology.ttl "
                f"declares it neither owl:FunctionalProperty nor as deliberately "
                f"set-valued. Declare one or the other, so a consumer can tell a "
                f"replacement from a second value."
            )
    return errors


def check_no_accumulation(og: Graph, graphs: list[Graph]) -> list[str]:
    """No subject holds two values AT ONCE for a declared functional property.

    The oracle materialises the whole state on every accepted act, so a property
    appended rather than set leaves a second value beside the first and the
    graph grows without bound. Checked within each graph rather than across
    them: a functional property may legitimately hold a DIFFERENT value after a
    later act, and comparing snapshots would flag every honest update.
    """
    errors: list[str] = []
    declared = functional_properties(og)
    if not declared:
        return errors
    for g in graphs:
        seen: dict[tuple[URIRef, URIRef], set] = {}
        for s, p, o in g:
            if isinstance(s, URIRef) and p in declared:
                seen.setdefault((s, p), set()).add(o)
        for (s, p), vals in sorted(seen.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
            if len(vals) > 1:
                shown = ", ".join(sorted(str(v) for v in vals))
                errors.append(
                    f"accumulation: <{s}> holds {len(vals)} values for "
                    f"{str(p).rsplit('/', 1)[-1]} ({shown}). It is declared "
                    f"functional, so re-encoding must replace the value, not "
                    f"append beside it."
                )
    return errors


def check_tbox(g: Graph) -> list[str]:
    """The ontology is a frozen schema: classes only, no individuals."""
    errors: list[str] = []
    classes = declared_classes(g)
    props = declared_properties(g)

    # Every ph: class has a GFO-light/GFO-core superclass, directly or through
    # a ph: intermediate. Transitive because a derived class should not have to
    # restate its grounding: a shared action is a Relator through
    # ph:PhysicalAction and carries no GFO superclass of its own.
    for c in sorted(classes, key=str):
        if not str(c).startswith(PH):
            continue
        if any(str(s).startswith((GFO_LIGHT, GFO_CORE)) for s in gfo_superclasses(g, c)):
            continue
        errors.append(f"ontology.ttl: class <{c}> lacks a GFO-light/GFO-core superclass")

    # Every `ph:` class a declaration NAMES is itself declared -- as a
    # superclass, a domain or a range. This is a different question from the
    # loop above, and it is not implied by it: grounding asks whether a class
    # REACHES GFO, and a dangling `ph:` superclass does not disturb that, because
    # the class keeps its own GFO grounding and the invented name rides alongside
    # it. A draft declaring `ph:BallotVote rdfs:subClassOf ph:SomethingNobody` and
    # one giving a property an undeclared domain both passed every check.
    #
    # It matters because that is the shape a drafting process produces when it
    # invents a class name and wires it in, which is exactly what the
    # clarification loop exists to prevent -- so a loop that stopped early would
    # otherwise be freezable. Only `ph:` names are required to resolve: a GFO
    # class is legitimately external, and grounding is what judges it.
    undeclared: dict[str, list[str]] = {}
    for subject in sorted({s for s in g.subjects() if isinstance(s, URIRef)}, key=str):
        if not str(subject).startswith(PH):
            continue
        for pred, slot in ((RDFS.subClassOf, "a subclass of"),
                           (RDFS.domain, "a domain of"),
                           (RDFS.range, "a range of")):
            for target in g.objects(subject, pred):
                if not isinstance(target, URIRef) or not str(target).startswith(PH):
                    continue
                if target in classes:
                    continue
                undeclared.setdefault(str(target), []).append(
                    f"<{subject}> is {slot} <{target}>")
    for target, uses in sorted(undeclared.items()):
        errors.append(
            f"ontology.ttl: <{target}> is named but not declared as a class, so "
            f"the declarations that use it ({'; '.join(sorted(uses))}) inherit "
            f"from nothing and a consumer cannot tell what they mean"
        )

    # Anything else named in the file is an individual, which belongs in
    # population.ttl or is minted at runtime.
    for subj in sorted({s for s in g.subjects() if isinstance(s, URIRef)}, key=str):
        if subj in classes or subj in props or str(subj).startswith(IMPORTED):
            continue
        errors.append(
            f"ontology.ttl: <{subj}> is an individual. The ontology is a frozen "
            f"TBox: declare the CLASS in ontology.ttl and the seeded individual "
            f"in population.ttl."
        )
    return errors


def check_population(pg: Graph, og: Graph) -> list[str]:
    """Seed individuals: typed, and citizens carry label and age."""
    errors: list[str] = []
    classes = declared_classes(og)
    citizen = expand("ph:Citizen")
    label = expand(FRAMEWORK_LABEL)
    age = expand("ph:age")

    for subj in sorted({s for s in pg.subjects() if isinstance(s, URIRef)}, key=str):
        types = [t for t in pg.objects(subj, RDF.type) if isinstance(t, URIRef)]
        if not types:
            errors.append(
                f"population.ttl: <{subj}> has no rdf:type, so a consumer "
                f"cannot tell what it is"
            )
            continue
        for t in types:
            if t not in classes and not str(t).startswith(IMPORTED):
                errors.append(
                    f"population.ttl: <{subj}> is typed <{t}>, which ontology.ttl "
                    f"does not declare as a class"
                )
        if citizen in types:
            if list(pg.objects(subj, label)) == []:
                errors.append(f"population.ttl: citizen <{subj}> lacks ph:label")
            if list(pg.objects(subj, age)) == []:
                errors.append(f"population.ttl: citizen <{subj}> lacks ph:age")
    return errors


def moment_classes(g: Graph) -> set[URIRef]:
    """The classes that ARE a moment: `gfo-light:TimeBoundary` or below it.

    A class, not an individual: the ontology is a frozen schema and holds no
    individuals, so the question is whether a subject's TYPE is a moment. A
    process instance, an occurrence, or a span is not one; `ph:Clock` and
    `ph:CalendarPoint` are, because the framework fixes both as subclasses of
    `gfo-light:TimeBoundary`.
    """
    return subclasses_of(g, URIRef(GFO_LIGHT + "TimeBoundary"))


def check_positions_are_moments(pg: Graph, og: Graph) -> list[str]:
    """`ph:dayIndex` / `ph:atHour` may sit only on a moment.

    Both properties are declared on `gfo-light:TimeBoundary`, so a subject
    outside that category carrying either one is a second copy of the present
    with no declared way to tell which copy was the real one. A consumer would
    otherwise have to know how many places a given law records the day.
    """
    errors: list[str] = []
    ok = moment_classes(og)
    for prop in ("ph:dayIndex", "ph:atHour"):
        p = expand(prop)
        for subj in sorted({s for s in pg.subjects(p, None) if isinstance(s, URIRef)},
                           key=str):
            types = {t for t in pg.objects(subj, RDF.type) if isinstance(t, URIRef)}
            if types & ok:
                continue
            named = ", ".join(sorted(str(t).rsplit("/", 1)[-1] for t in types)) or "nothing"
            errors.append(
                f"population.ttl: <{subj}> carries {prop} but is typed {named}, "
                f"which is not a gfo-light:TimeBoundary. A position belongs on "
                f"ph:Clock, on a ph:CalendarPoint, or on a bound the oracle "
                f"mints; a process instance or a span holds no present of its own."
            )
    return errors


def subclasses_of(g: Graph, root: URIRef) -> set[URIRef]:
    """Every class transitively below `root`, computed by hand.

    rdflib performs no reasoning, so the gate walks rdfs:subClassOf itself
    rather than trusting entailment it will never get.
    """
    found: set[URIRef] = {root}
    frontier = [root]
    while frontier:
        parent = frontier.pop()
        for child in g.subjects(RDFS.subClassOf, parent):
            if isinstance(child, URIRef) and child not in found:
                found.add(child)
                frontier.append(child)
    return found


def gfo_superclasses(g: Graph, cls: URIRef) -> set[URIRef]:
    """Every ancestor of `cls` through rdfs:subClassOf, walked upward.

    The mirror image of `subclasses_of`, and needed for the same reason: rdflib
    performs no reasoning, so grounding is established by walking the chain
    rather than by trusting entailment.
    """
    found: set[URIRef] = set()
    frontier = [cls]
    while frontier:
        node = frontier.pop()
        for parent in g.objects(node, RDFS.subClassOf):
            if isinstance(parent, URIRef) and parent not in found:
                found.add(parent)
                frontier.append(parent)
    return found


def process_classes(g: Graph) -> set[URIRef]:
    """Every ph: class that is a gfo-core:Process."""
    return {c for c in declared_classes(g) if c in subclasses_of(g, PROCESS)}


def phase_graph(g: Graph) -> tuple[set[URIRef], set[URIRef]]:
    """(containers, phases) over ph:hasPhase between declared classes."""
    procs = process_classes(g)
    containers = {s for s in g.subjects(HAS_PHASE, None) if s in procs}
    phases = {o for o in g.objects(None, HAS_PHASE) if o in procs}
    return containers, phases


def reachable_phases(g: Graph) -> set[URIRef]:
    """Phases reachable from a root Process by following ph:hasPhase."""
    containers, _ = phase_graph(g)
    reached: set[URIRef] = set()
    frontier = list(containers)
    while frontier:
        node = frontier.pop()
        for phase in g.objects(node, HAS_PHASE):
            if phase not in reached:
                reached.add(phase)
                if phase in containers:
                    frontier.append(phase)
    return reached


def grounded_processes(g: Graph, reached: set[URIRef]) -> set[URIRef]:
    """Reached Processes plus every ancestor of one.

    A law's own process is a SPECIALISATION of a shared physical process --
    `ph:CastVote rdfs:subClassOf ph:Deposit` -- so the shared class is in the
    hierarchy by being the superclass of something the law reaches, not by
    being named in `ph:hasPhase`. Without this the only way a law could
    reach a shared physical action would be to declare it as one of its own
    phases, which would make the shared action a phase of every law that
    performs it and put the physical vocabulary back where it started.

    The relaxation is bounded in the same way `check_tbox`'s transitive
    superclass walk is: a stray Process with no reached descendant is still
    an orphan, and a law cannot make one reachable by inventing a subclass
    of it and nothing else.
    """
    grounded: set[URIRef] = set(reached)
    for r in reached:
        grounded |= {a for a in gfo_superclasses(g, r) if a in process_classes(g)}
    return grounded


def check_phase_reachability(g: Graph, own_classes: set[URIRef] | None = None) -> list[str]:
    """Every Process class the LAW declares is reachable (6.4).

    Scoped to the law's own declarations, because reachability is a question
    about a law's hierarchy and the shared vocabulary is not part of one. A
    shared physical action no law has specialised into yet is unused
    framework vocabulary, not a phase of this law that a consumer would fail
    to find -- and it is reachable by definition as soon as any law
    subclasses a reached Process into it.

    `own_classes` is the law's own declared classes; `None` means "every
    Process in the graph", which is the pre-vocabulary behaviour.
    """
    procs = process_classes(g)
    if own_classes is not None:
        procs &= own_classes
    reached = reachable_phases(g)
    containers, _ = phase_graph(g)
    grounded = grounded_processes(g, reached) | containers
    errors: list[str] = []
    for c in sorted(procs - grounded, key=str):
        errors.append(
            f"phase hierarchy: <{c}> is a gfo-core:Process that no declared root "
            f"reaches through ph:hasPhase and no reached Process specialises into "
            f"it. A consumer reads the hierarchy to know what the law is made of; "
            f"an unreachable class is in neither."
        )
    return errors


def check_no_orphan_process(
    g: Graph, pg: Graph, manifest: dict | None,
    own_classes: set[URIRef] | None = None,
) -> list[str]:
    """No Process class the LAW declares is referenced by nothing at all (6.5).

    A declared Process class is live if something in the artefact set can
    reach it: another Process contains it through ph:hasPhase, a reached
    Process specialises into it, the manifest names it as an ECA's process,
    or the seeded graph has an individual typed with it. Reachability alone
    cannot tell a real root from a stray one — both are Processes that contain
    nothing and are contained by nothing — so the seeded individual is what
    settles it.

    Scoped to the law's own declarations for the same reason as
    `check_phase_reachability`: a shared physical action belongs to the
    framework, and whether this law performs it is not a question about
    whether the law is coherent.
    """
    procs = process_classes(g)
    if own_classes is not None:
        procs &= own_classes
    _, phases = phase_graph(g)
    named: set[URIRef] = set()
    minted: set[URIRef] = set()
    if manifest:
        for e in manifest.get("ecas", []):
            named.add(expand(f"ph:{e.get('eca_process', '')}"))
            # An ECA that mints a new instance declares the class it creates
            # (law-framework: an ECA whose action mints a new Process instance
            # SHALL name the Process class it creates). A law whose instances
            # are all runtime-minted has no seeded individual to show the class
            # is real, so this declaration is the only thing that keeps it from
            # reading as an orphan.
            if e.get("mints"):
                minted.add(expand(f"ph:{e['mints']}"))
    instantiated = {
        t for t in pg.objects(None, RDF.type) if isinstance(t, URIRef)
    } | {
        t for c in procs for t in pg.subjects(RDF.type, c)
    }
    # A shared physical process is live once a reached Process specialises
    # into it, for the same reason it is reachable: the law's own process IS
    # that physical event under the law's name. Without this every law
    # drawing on a shared action would report all three of them as orphans.
    live = phases | named | minted | instantiated | grounded_processes(
        g, reachable_phases(g)
    )

    errors: list[str] = []
    for c in sorted(procs - live, key=str):
        errors.append(
            f"orphan Process class: <{c}> is declared but nothing in the law reaches "
            f"it — no root contains it through ph:hasPhase, no reached Process "
            f"specialises into it, no manifest eca_process names it, and the seeded "
            f"graph has no individual typed with it. Declare it as a phase of a "
            f"Process, subclass a reached Process into it, name it in the manifest, "
            f"or delete it."
        )
    return errors


def check_phase_calendar_spans(g: Graph, pg: Graph) -> list[str]:
    """Every declared phase is marked by a calendar node (6.6)."""
    _, phases = phase_graph(g)
    if not phases:
        return []
    # marksPhase naming a phase class lives wherever the frozen base calendar
    # lives — the schema for a class-level marking, the seeds for the
    # calendar individuals that do the marking in practice.
    marked: dict[URIRef, list[URIRef]] = {}
    for src in (g, pg):
        for _, _, obj in src.triples((None, MARKS_PHASE, None)):
            if obj in phases:
                marked.setdefault(obj, []).append(src)
    errors: list[str] = []
    for phase in sorted(phases - set(marked), key=str):
        errors.append(
            f"calendar span: phase <{phase}> is declared but no ph:CalendarSpan or "
            f"ph:CalendarPoint marks it with ph:marksPhase, so no consumer can tell "
            f"when it happens"
        )
    return errors


def check_no_phase_ordering(g: Graph, pg: Graph) -> list[str]:
    """No ordering relation between two declared phases (6.7)."""
    _, phases = phase_graph(g)
    errors: list[str] = []
    for src in (g, pg):
        for subj, pred, obj in src:
            local = str(pred).rsplit("/", 1)[-1].rsplit("#", 1)[-1]
            if local not in ORDERING_PROPS:
                continue
            where = "ontology.ttl" if src is g else "population.ttl"
            for a, b in ((subj, obj), (obj, subj)):
                if a in phases and b in phases:
                    errors.append(
                        f"phase ordering: {where} asserts <{pred}> from <{a}> to <{b}>. "
                        f"Sequencing belongs in the calendar bounds — give each phase a "
                        f"ph:CalendarPoint or ph:CalendarSpan carrying ph:marksPhase and "
                        f"ph:dayIndex, and drop the ordering relation. A schema-level "
                        f"order duplicates the schedule and cannot be checked against it."
                    )
    return errors


def instance_is(g: Graph, pg: Graph, node: URIRef, category: URIRef, classes: set[URIRef]) -> bool:
    """Is `node` asserted to be in `category`? Reasoning done by hand.

    An individual is in the category when one of its asserted types is a
    class below the category, or when it is itself typed by the category.
    """
    if node in subclasses_of(g, category) & classes:
        return True
    for t in pg.objects(node, RDF.type):
        if t in subclasses_of(g, category):
            return True
    return False


def check_caused_by(g: Graph, pg: Graph) -> list[str]:
    """ph:causedBy runs Process -> gfo-core:State (6.8).

    It states a permitted dependency that a Lean guard evaluates. It is not
    a mechanism for ordering phases, and the direction is not negotiable:
    a State may bring about a change in a Process, never the reverse.
    """
    errors: list[str] = []
    classes = declared_classes(g)
    procs = subclasses_of(g, PROCESS)
    states = subclasses_of(g, STATE)
    for subj, _, obj in pg.triples((None, CAUSED_BY, None)):
        where = "population.ttl"
        if not isinstance(subj, URIRef) or not isinstance(obj, URIRef):
            continue
        # Subject must be a Process.
        if subj not in procs and not any(
            t in procs for t in pg.objects(subj, RDF.type)
        ):
            errors.append(
                f"causedBy: {where} asserts <{subj}> ph:causedBy <{obj}>, but "
                f"<{subj}> is not a gfo-core:Process. The relation runs "
                f"Process -> State: a State may bring about a change in a Process, "
                f"and nothing else may cause anything."
            )
            continue
        if obj not in states and not any(t in states for t in pg.objects(obj, RDF.type)):
            errors.append(
                f"causedBy: {where} asserts <{subj}> ph:causedBy <{obj}>, but "
                f"<{obj}> is not a gfo-core:State. The relation runs "
                f"Process -> State; for ordering between phases use the calendar "
                f"bounds, not ph:causedBy."
            )
    return errors


def check_manifest_against_oracle(case: Path, og: Graph) -> list[str]:
    """The manifest and the oracle must describe the same law (6.9).

    Two declaration sites name the ECAs — the manifest and the compiled
    oracle — and a law where they disagree is a law whose TUI offers duties
    the oracle will reject, or hides duties it will accept. The ontology is
    the third: every Role the manifest names must be one the ontology
    declares as participating in that ECA's Process.
    """
    errors: list[str] = []
    try:
        manifest = yaml.safe_load((case / "manifest.yaml").read_text()) or {}
    except Exception as e:  # noqa: BLE001 - reported by check_manifest
        return [f"manifest.yaml: cannot cross-validate, YAML parse failed: {e}"]

    binary = case / "oracle"
    if not binary.exists():
        errors.append(
            f"oracle: {binary.name} is not built, so the manifest cannot be "
            f"cross-validated against `oracle list`. Run tools/lawgen/build_oracle.py first."
        )
    else:
        proc = subprocess.run(
            [str(binary), "list"], capture_output=True, text=True, timeout=60
        )
        if proc.returncode != 0:
            errors.append(f"oracle: `oracle list` failed (exit {proc.returncode})")
        else:
            try:
                served = set(json.loads(proc.stdout).get("ecas", []))
            except Exception as e:  # noqa: BLE001
                errors.append(f"oracle: `oracle list` did not return readable JSON: {e}")
                served = None
            if served is not None:
                declared = {e.get("id") for e in manifest.get("ecas", [])}
                for missing in sorted(served - declared):
                    errors.append(
                        f"manifest.yaml: `oracle list` offers eca '{missing}' but the "
                        f"manifest does not declare it, so no consumer would ever offer it"
                    )
                for extra in sorted(declared - served):
                    errors.append(
                        f"manifest.yaml: eca '{extra}' is declared but `oracle list` does "
                        f"not serve it, so the TUI would offer a duty the oracle refuses"
                    )

    participants: dict[URIRef, set[URIRef]] = {}
    for proc_cls, role in og.subject_objects(HAS_PARTICIPANT):
        participants.setdefault(proc_cls, set()).add(role)
    roles = declared_classes(og)

    for e in manifest.get("ecas", []):
        eca_id = e.get("id")
        proc_cls = expand(f"ph:{e.get('eca_process', '')}")
        allowed = participants.get(proc_cls, set())
        if not allowed:
            errors.append(
                f"manifest.yaml: eca '{eca_id}' names process "
                f"{e.get('eca_process')!r}, which ontology.ttl declares no "
                f"ph:hasParticipant Roles for, so nothing can hold the duty"
            )
            continue
        for slot, role in [("holder_role", e.get("holder_role"))] + [
            (f"params[{p.get('name')}]", p.get("role"))
            for p in (e.get("params") or [])
        ]:
            ref = expand(f"ph:{role}") if role else None
            if ref is None or ref not in roles:
                errors.append(
                    f"manifest.yaml: eca '{eca_id}' {slot} names '{role}', which "
                    f"ontology.ttl does not declare as a class"
                )
            elif ref not in allowed:
                errors.append(
                    f"manifest.yaml: eca '{eca_id}' {slot} names '{role}', which "
                    f"ontology.ttl does not declare a participant of "
                    f"{e.get('eca_process')!r} (it declares "
                    f"{', '.join(sorted(str(r).rsplit('/', 1)[-1].rsplit('#', 1)[-1] for r in allowed))})"
                )
    return errors


# Clock positions a driver could plausibly write but no calendar describes.
# The driver owns the clock, so the oracle receives it as untrusted input and
# owes totality: every one of these must produce a well-formed verdict, not a
# crash and not a silent nonsense answer.
CLOCK_PROBES = [
    (0, 0),        # the seed position
    (0, 23),       # last hour of the first day
    (0, 99),       # an hour no clock has
    (1, 0),        # one minute either side of midnight
    (9, 12),       # mid-election
    (10, 19),      # polls closing
    (10, 20),      # just after
    (1461, 10),    # one whole cycle later
    (999_999, 23),  # far outside the calendar
]


def _client(case: Path):
    """The compiled oracle plus the seeded graph, or an error string."""
    sys.path.insert(0, str(ROOT))
    from runtime.graphwire import WorldDriftError
    from runtime.oracle import OracleClient

    try:
        return OracleClient(case), None
    except (FileNotFoundError, WorldDriftError) as e:
        return None, [str(e)]


def check_clock_monotonicity(case: Path) -> list[str]:
    """A clock rewound past a recorded moment admits no act the graph forbids.

    Total and monotone are separate guarantees. Totality says no value can crash
    the oracle; monotonicity says no value may contradict a moment the graph
    already holds.

    It probes the GUARDS, not the OFFERS. An earlier version asked what the
    verdict was advertising and replayed that, which cannot see a guard that
    disagrees with its own offerability -- the hazard this exists to catch. So a
    complete act is captured for each ECA at the moment it is legitimately
    offered, when its parameters are known good, and replayed afterwards. What is
    under test is the transition function, not the advertisement.

    Two findings, and the second is the requirement's own words:

    - an act that was refused and is accepted once the clock is rewound;
    - an act accepted into a process instance that carries a FINISH bound,
      whether or not the rewind is what enabled it.
    """
    client, errs = _client(case)
    if client is None:
        return errs
    errors: list[str] = []
    by_id = manifest_of(case)

    # Capture a complete act per ECA while it is legitimately offered, and walk
    # far enough for the law to have recorded a moment.
    cached: dict[str, dict] = {}
    saved: dict | None = None
    floor: tuple[int, int] | None = None
    for day, hour in _drive_stops(client):
        client.set_clock(day, hour)
        for act in pending_acts(client, by_id):
            cached.setdefault(act["eca"], act)
        play_forward(client, by_id, limit=1)
        recorded = _recorded_moments(client)
        if recorded and (floor is None or max(recorded) > floor):
            saved, floor = {"graph": graph_to_wire(client.graph)}, max(recorded)
    if saved is None or floor is None:
        return ["clock monotonicity: no moment is recorded in any driven state, "
                "so there is nothing to rewind past and the check proved nothing"]
    if not cached:
        return ["clock monotonicity: no ECA was ever offered, so there is no act "
                "to replay and the check proved nothing"]

    floor_day, floor_hour = floor
    # Rewind to the moments the LAW ITSELF declares that fall before the floor:
    # those are exactly where a closed period could be open again.
    targets = [(d, h) for d, h in calendar_moments(client) if (d, h) < floor]
    if floor_day > 0:
        targets.append((floor_day - 1, floor_hour))
    if not targets:
        return [f"clock monotonicity: the only moment this law records is day "
                f"{floor_day} hour {floor_hour} and it declares no earlier one, "
                f"so there is nothing to rewind to and the check proved nothing"]

    # What each cached act does from the state the law actually reached.
    # Every replay is evaluated from that state and then unwound: an accepted
    # replay mutates the graph (a repeat mints its successor, a count stamps
    # its flag), and without rewinding, one replay's side effects become the
    # next replay's world -- manufacturing findings out of the probe's own
    # acts rather than the law's guards. Totality already probes this way
    # (see `_reset`); monotonicity was the holdout.
    client.replace(wire_to_graph(saved["graph"]))
    before: dict[str, str | None] = {}
    for eca, act in cached.items():
        snap = {"graph": graph_to_wire(client.graph)}
        before[eca] = _refusal_for(client, act)
        client.replace(wire_to_graph(snap["graph"]))
    client.replace(wire_to_graph(saved["graph"]))

    for rday, rhour in sorted(set(targets)):
        client.set_clock(rday, rhour)
        finished = _finished_instances(client)
        for eca, act in sorted(cached.items()):
            snap = {"graph": graph_to_wire(client.graph)}
            why = _refusal_for(client, act)
            client.replace(wire_to_graph(snap["graph"]))
            closed = sorted(v for v in act.values()
                            if isinstance(v, str) and v in finished)
            if why is None and closed:
                errors.append(
                    f"clock monotonicity: with the clock rewound to day {rday} "
                    f"hour {rhour}, `{eca}` was accepted into "
                    f"{', '.join(x.rsplit('/', 1)[-1] for x in closed)}, which "
                    f"carries a finish bound. A recorded moment must not be "
                    f"undoable by moving the clock."
                )
            elif why is None and before[eca] is not None:
                errors.append(
                    f"clock monotonicity: with the clock rewound to day {rday} "
                    f"hour {rhour}, `{eca}` was accepted, where at day "
                    f"{floor_day} hour {floor_hour} it was refused "
                    f"({before[eca]!r}). A recorded moment must not be undoable "
                    f"by moving the clock."
                )
    return errors


def _drive_stops(client) -> list[tuple[int, int]]:
    """Every declared calendar moment, plus a far-future last resort.

    The sentinel is not used as a FLOOR: an act performed at day 1000000 is not
    a moment any law would record, and since its day is astronomically larger it
    would win any "richest record" contest by construction.
    """
    return sorted(set(calendar_moments(client))) + [(10 ** 6, 10)]


def _finished_instances(client) -> set[str]:
    """Every Process instance in the graph carrying a finish bound."""
    out: set[str] = set()
    for subj in client.graph.subjects(RDF.type, None):
        chrono = client.graph.value(URIRef(str(subj)), expand("ph:hasTime"))
        if chrono is None:
            continue
        if client.graph.value(chrono, expand("gfo-core:temporallyFinishedBy")) \
                is not None:
            out.add(str(subj))
    return out


def check_chronoid_shape(og: Graph, graphs: list[Graph]) -> list[str]:
    """Every Process instance in the runtime graph reaches a Chronoid.

    law-framework: "Process instances SHALL take their temporal bounds in GFO's
    shape: an instance relates to a `Chronoid` by `ph:hasTime`". A flat law that
    kept its whole election state in one individual with no `Chronoid` at all was
    conforming under every other check -- nothing looked. It surfaced only
    because monotonicity needs a recorded moment to rewind past and found none,
    which is the wrong place to discover a missing shape.

    Only ROOT Process classes are required one -- the classes nothing declares as
    a phase of another Process. The occurrence individuals inside an instance are
    its phases: a nomination is a `SelfNomination`, a ballot a `BallotVote`, a
    cast vote a `CastVote`, and each appears as an object of some `ph:hasPhase`.
    They are addressed through their enclosing instance and no shipped law gives
    those their own `Chronoid`, so requiring one here would fail laws the
    framework does not ask to fail.
    """
    if not graphs:
        return ["chronoid shape: no runtime graph was available, so this check "
                "proved nothing"]
    is_phase = {str(o) for o in og.objects(None, expand("ph:hasPhase"))}
    proc_classes = {str(c) for c in process_classes(og)} - is_phase
    if not proc_classes:
        return ["chronoid shape: every Process class is a phase of another, so "
                "this law declares no root instance and the check proved nothing"]
    errors: list[str] = []
    seen = False
    for g in graphs:
        for subj in sorted({str(s) for s in g.subjects(RDF.type, None)}):
            types = {str(t) for t in g.objects(URIRef(subj), RDF.type)}
            if not (types & proc_classes):
                continue
            seen = True
            chrono = g.value(URIRef(subj), expand("ph:hasTime"))
            if chrono is None:
                errors.append(
                    f"chronoid shape: {subj.rsplit('/', 1)[-1]} is a "
                    f"gfo-core:Process but relates to no Chronoid by ph:hasTime, "
                    f"so it cannot say whether it has begun or ended"
                )
                continue
            chrono_types = {str(t) for t in g.objects(chrono, RDF.type)}
            if str(CHRONOID) not in chrono_types:
                errors.append(
                    f"chronoid shape: {subj.rsplit('/', 1)[-1]} relates by "
                    f"ph:hasTime to <{str(chrono).rsplit('/', 1)[-1]}>, which is "
                    f"not typed gfo-light:Chronoid "
                    f"(it is {sorted(t.rsplit('/', 1)[-1] for t in chrono_types) or 'untyped'})"
                )
    if not seen:
        return ["chronoid shape: no Process instance appeared in any runtime "
                "graph, so this check proved nothing"]
    return errors


def _phrase(v: str | None) -> str:
    """How a probe result reads in a finding."""
    if v is None:
        return "accepted"
    if v == NOT_OFFERED:
        return "not offered"
    return f"refused ({v!r})"


def _recorded_moments(client) -> list[tuple[int, int]]:
    """Every moment the graph records on a Chronoid bound, as (day, hour)."""
    return sorted(
        (int(str(d)), int(str(h)))
        for b in client.graph.subjects(RDF.type, URIRef(TIME_BOUNDARY))
        for d, h in [(client.graph.value(b, expand("ph:dayIndex")),
                      client.graph.value(b, expand("ph:atHour")))]
        if d is not None and h is not None
    )


def _accepts(client, case: Path) -> dict[str, str | None]:
    """Every declared ECA: None if accepted here, else the refusal text.

    Probed from a snapshot so the before and after readings start from the same
    state -- `apply` moves the law on, so without restoring, the second reading
    would be of a later world than the first.
    """
    by_id = manifest_of(case)
    wire = {"graph": graph_to_wire(client.graph)}
    out: dict[str, str | None] = {}
    for eca_id in by_id:
        acts = _acts_for(client, by_id, eca_id)
        out[eca_id] = _refusal_for(client, acts[0]) if acts else NOT_OFFERED
    client.replace(wire_to_graph(wire["graph"]))
    return out


def _acts_for(client, by_id: dict, eca_id: str) -> list[dict]:
    """A complete act for `eca_id`, from the manifest and the verdict."""
    eca = by_id[eca_id]
    for citizen, entries in (client.check().get("pending") or {}).items():
        for entry in entries:
            if isinstance(entry, str):
                if entry != eca_id:
                    continue
                act = act_from_declaration(eca, {}, citizen)
                return [act] if act else []
            if entry.get("eca") != eca_id:
                continue
            act = act_from_declaration(eca, entry, citizen)
            if act:
                return [act]
    return []


def _refusal_for(client, act: dict) -> str | None:
    """None if `act` is accepted, else the guard it was refused by."""
    try:
        client.apply(act)
        return None
    except Exception as e:  # noqa: BLE001 - the refusal text is the finding
        return str(e)


def check_clock_totality(case: Path) -> list[str]:
    """`check` and `apply` are total over the clock (6.10).

    The driver writes `ph:Clock` and nothing else, which makes the clock
    untrusted input to Lean. A pattern match that misses, or a Nat
    subtraction that underflows, turns a legal clock position into a crash
    the consumer cannot interpret.
    """
    client, errs = _client(case)
    if client is None:
        return errs
    errors: list[str] = []
    for day, hour in CLOCK_PROBES:
        client.set_clock(day, hour)
        try:
            verdict = client.check()
        except Exception as e:  # noqa: BLE001 - a crash is the finding
            errors.append(f"clock totality: `check` failed at day {day} hour {hour}: {e}")
            continue
        missing = [k for k in ("fired", "pending", "violations", "phase") if k not in verdict]
        if missing:
            errors.append(
                f"clock totality: `check` at day {day} hour {hour} returned no "
                f"{', '.join(missing)}"
            )
        # `apply` must answer too — a rejection is fine and expected off-schedule,
        # a crash or an unreadable answer is not.
        for eca in client.eca_ids():
            act = {"eca": eca}
            if eca == "nominate":
                citizens = sorted(
                    str(s)
                    for s in client.graph.subjects(
                        URIRef(RDF.type), expand("ph:Citizen")
                    )
                )
                if citizens:
                    act["citizen"] = citizens[0]
            if eca == "vote":
                candidates = sorted(
                    str(s)
                    for s in client.graph.subjects(
                        URIRef(RDF.type), expand("ph:CandidateRole")
                    )
                )
                voters = sorted(
                    str(s)
                    for s in client.graph.subjects(
                        URIRef(RDF.type), expand("ph:Citizen")
                    )
                )
                if candidates and voters:
                    act["voter"] = voters[0]
                    act["candidate"] = candidates[0]
            try:
                client.apply(dict(act))
            except Exception as e:  # noqa: BLE001
                from runtime.oracle import OracleRejected

                if not isinstance(e, OracleRejected):
                    errors.append(
                        f"clock totality: `apply {eca}` failed at day {day} hour "
                        f"{hour} with something other than a rejection: {e}"
                    )
                # Restore the seeded position for the next probe.
                client = _reset(client)
    return errors


def _reset(client):
    """Reload the seeded graph so one probe cannot influence the next."""
    from runtime.oracle import OracleClient

    fresh = OracleClient(client.case)
    client.graph = fresh.graph
    return client


def _manifest_of(case: Path) -> tuple[dict, list[str]]:
    try:
        return yaml.safe_load((case / "manifest.yaml").read_text()) or {}, []
    except Exception as e:  # noqa: BLE001 - reported by check_manifest
        return {}, [f"manifest.yaml: cannot read: {e}"]


def check_reading_declarations(case: Path, og: Graph) -> list[str]:
    """Every reading the oracle emits is declared in the manifest (5.6).

    A reading is the one part of the verdict a consumer cannot derive: it has
    an id the law chose and a class it resolves through, so an undeclared one
    is unrenderable. The manifest is the single declaration site, and the gate
    checks both directions that are checkable -- every EMITTED reading is
    declared, and every declared `class` is a real class.

    A declared reading the oracle has not emitted is NOT an error: a law may
    have results it has not reached. quorum's `quorumHeld` is absent until its
    cycle is counted precisely so that "not yet determined" reads differently
    from "determined, and false".
    """
    manifest, errs = _manifest_of(case)
    if errs:
        return errs
    declared = manifest.get("readings")
    if declared is None:
        return [
            "manifest.yaml: declares no readings block, so no consumer can render a "
            "result. Declare each reading the oracle may emit with its id, the class "
            "a `ref` reading resolves through, a label, and a template."
        ]

    errors: list[str] = []
    classes = declared_classes(og)
    ids = [r.get("id") for r in declared]
    if len(ids) != len(set(ids)):
        errors.append("manifest.yaml: duplicate reading ids")
    for r in declared:
        rid = r.get("id")
        if not rid:
            errors.append("manifest.yaml: a readings entry declares no id")
            continue
        for field in ("label", "template"):
            if not r.get(field):
                errors.append(
                    f"manifest.yaml: reading '{rid}' declares no {field}, so a "
                    f"consumer has nothing to display"
                )
        cls = r.get("class")
        if cls is not None and expand(f"ph:{cls}") not in classes:
            errors.append(
                f"manifest.yaml: reading '{rid}' names class '{cls}', which "
                f"ontology.ttl does not declare"
            )

    client, cerrs = _client(case)
    if client is None:
        return errors + cerrs
    by_id = {e.get("id"): e for e in manifest.get("ecas", [])}
    try:
        play_forward(client, by_id)
        emitted = client.check().get("readings") or []
    except Exception as e:  # noqa: BLE001
        return errors + [
            f"readings: could not drive the law to a result state: {e}"
        ]

    if not emitted:
        errors.append(
            "readings: the oracle emitted no reading even after being driven to a "
            "result state, so this check proved nothing"
        )
    by_decl = {r.get("id"): r for r in declared}
    for reading in emitted:
        rid = reading.get("id")
        if rid not in by_decl:
            errors.append(
                f"manifest.yaml: the oracle emits reading '{rid}' but the readings "
                f"block does not declare it, so a consumer cannot render it"
            )
            continue
        # A ref reading must resolve through the class the manifest declares, or
        # the label the consumer looks up belongs to a different concept.
        want = by_decl[rid].get("class")
        got = reading.get("refClass")
        if got is not None and want is None:
            errors.append(
                f"manifest.yaml: reading '{rid}' is a `ref` reading pointing at "
                f"{got}, but the declaration resolves through nothing; declare the "
                f"class so the label resolves"
            )
        elif got is not None and want is not None and PH + want != got:
            errors.append(
                f"manifest.yaml: reading '{rid}' declares class '{want}' but the "
                f"oracle resolves it through {got}"
            )
    return errors


def check_graph_roundtrip(case: Path) -> list[str]:
    """The graph survives `apply`, and re-checking agrees (6.11).

    The graph is the snapshot, so a transition that loses or retypes an
    individual is a silent corruption of the only state there is. `apply`
    returning the whole graph is what lets the consumer replace wholesale;
    that is only safe if the answer is complete and stable.

    The graph is played forward rather than inspected once, because the seed
    alone offers nothing to apply: an unopened law has no ballots and no
    candidates, so there is no act to round-trip until earlier acts have
    happened. Acts are built from the manifest's own declarations, so this
    doubles as a check that the manifest is sufficient on its own.
    """
    client, errs = _client(case)
    if client is None:
        return errs

    from runtime.oracle import OracleRejected, UndeclaredSubject

    manifest, merrs = _manifest_of(case)
    if merrs:
        return merrs
    by_id = {e.get("id"): e for e in manifest.get("ecas", [])}

    errors: list[str] = []
    applied, losses = play_forward(client, by_id)
    for lost in losses:
        errors.append(
            f"graph round trip: `apply` removed {lost}. Erasure is prohibited: "
            f"the only revisable fact is counting."
        )

    if not applied and not errors:
        errors.append(
            "graph round trip: no act could be applied from the seeded graph, so "
            "the round trip proved nothing"
        )

    # Two checks on an unchanged graph must agree: `check` is a function of
    # the graph, so it may not drift with call order or hidden state.
    try:
        first = client.check()
        second = client.check()
    except Exception as e:  # noqa: BLE001
        return errors + [f"graph round trip: `check` after `apply` failed: {e}"]
    if first != second:
        differing = sorted(k for k in set(first) | set(second) if first.get(k) != second.get(k))
        errors.append(
            f"graph round trip: two `check` calls on the same graph disagreed on "
            f"{', '.join(differing)}"
        )

    # Anything the oracle minted must be typed by a class the ontology knows.
    # GFO categories count: a Chronoid is a gfo-light:Chronoid, not a ph: one,
    # and the framework is grounded rather than re-declaring GFO's own types.
    for subj in sorted(client.subjects()):
        if not subj.startswith(PH):
            continue
        types = [
            str(o)
            for o in client.graph.objects(URIRef(subj), URIRef(RDF.type))
            if str(o).startswith(PH) or str(o).startswith((GFO_LIGHT, GFO_CORE))
        ]
        if not types:
            errors.append(
                f"graph round trip: <{subj}> is in the graph but carries no type the "
                f"law's ontology or GFO declares, so a consumer cannot tell what it is"
            )
    return errors


def check_verdict_is_total(client, verdict: dict, label: str,
                           creating: set[str] | None = None) -> list[str]:
    """Nothing a verdict names may be absent from the graph.

    This is the observable half of "the graph is total over the world": the
    oracle derives its state from the graph, so a verdict that names something
    the graph does not contain is describing a fact no consumer could resolve,
    display, or audit. It is the failure the earlier `apply`-response type check
    cannot see, because that check looks at what the oracle WROTE and this looks
    at what it then pointed at.
    """
    errors: list[str] = []
    present = client.subjects()

    def check_iri(value, where: str) -> None:
        if isinstance(value, str) and value.startswith(PH) and value not in present:
            errors.append(
                f"totality: {label} {where} names <{value}>, which the graph does "
                f"not contain. A verdict may only name what a consumer can resolve."
            )

    for entry in verdict.get("readings") or []:
        if entry.get("kind") == "ref":
            check_iri(entry.get("value"), f"reading {entry.get('id')!r}")
    check_iri(verdict.get("phase"), "phase")
    creating = creating or set()
    for citizen, entries in (verdict.get("pending") or {}).items():
        check_iri(citizen, "pending holder")
        for entry in entries or []:
            # A duty that CREATES the instance it names is the one licence to
            # name something absent: lodging names the requisition it is about
            # to bring into being. Anything else must name what is in the graph.
            if entry.get("eca") in creating:
                continue
            check_iri(entry.get("process"), f"pending {entry.get('eca')!r} process")
    for violation in verdict.get("violations") or []:
        witness = violation.get("witness") or {}
        for ref in witness.get("refs") or []:
            check_iri(ref, f"violation {violation.get('eca')!r} witness")
    return errors



def check_seed_parity(case: Path, pg: Graph) -> list[str]:
    """A seeded property the oracle never names at all is a second source.

    Narrower than "no guard reads this", and narrow on purpose. Whether a
    condition consults a property is a fact about the oracle's code and is not
    observable from outside: a property read only on a path a given walk never
    takes — `ph:age` for an oldest-citizen tie-break, say — looks unread to any
    black-box probe, so asking the oracle and comparing verdicts produces false
    positives on every legitimately-consulted property.

    What IS observable, and is the case that actually occurred, is a `ph:`
    property that `rules.lean` never mentions. No guard can read a predicate the
    oracle does not name, so a seeded value on such a property is held for
    nobody — which is what `ph:repeatGapDays` was: declared, seeded, and read by
    nothing, duplicating the Lean constant `repeatGap`.

    Only properties seeded on an individual are tested. A relation the law
    declares for a reader rather than for a condition — `ph:causedBy`,
    `ph:hasPhase` — appears in the ontology and the seed on purpose and is
    never named in Lean, which is the whole point of those two.

    Scoped to the law's own seeds, not the merged graph: the caller passes
    the case's seeds without the shared world. World furniture a law never
    names is available, not duplicated — judging it here would fail every
    law that presupposes less than the whole world.
    """
    import re

    errors: list[str] = []
    seeded = {str(pr) for pr in pg.predicates(None, None) if str(pr).startswith(PH)}
    seeded.discard(PH + "label")
    if not seeded:
        return ["seed parity: the seed carries no ph: property, so this check "
                "proved nothing"]

    try:
        lean = (case / "rules.lean").read_text()
    except OSError as e:
        return [f"seed parity: could not read rules.lean: {e}"]

    named = set(re.findall(r'ph\s+"([A-Za-z]+)"', lean))
    unnamed = sorted(p[len(PH):] for p in seeded if p[len(PH):] not in named)
    exempt = SET_VALUED_BY_DESIGN | CLASS_LEVEL_ONLY | FRAMEWORK_OWN_VOCABULARY
    for short in unnamed:
        if short in exempt:
            continue
        holders = sorted({
            str(s).rsplit("/", 1)[-1]
            for s, pr, _ in pg.triples((None, URIRef(PH + short), None))
        })
        errors.append(
            f"seed parity: ph:{short} is seeded on {', '.join(holders[:4])} but "
            f"rules.lean never names it, so no guard can read it. A value nothing "
            f"consults is a second source for a fact rather than a description of "
            f"what the law permits; delete it, or make the law use it."
        )
    if not named:
        return ["seed parity: rules.lean names no ph: property at all, so this "
                "check proved nothing"]
    return errors


def check_role_shape(og: Graph, pg: Graph, snapshots: list[Graph]) -> list[str]:
    """A Role the ORACLE mints must relate both a context and a holder.

    Scoped to minted roles, because seeding role vocabulary is legitimate: a law
    may declare `ph:VoterRole`, `ph:CandidateRole` and the rest as labelled
    individuals so a consumer can resolve a role by IRI before anyone holds it,
    and `mayor-2027` does exactly that. Those carry a label and nothing else,
    which is the correct shape for a role nobody holds yet. Only a Role the
    oracle brings into being must have both ends, because that is a claim that
    somebody is playing it somewhere.

    Also checked: no subject holds the same Role twice in one situation, and no
    subject's declared class changes between snapshots. Meaning is a relation,
    not a change of type, so a class that changes with a process's progress
    leaves the graph unreadable at any fixed point.
    """
    errors: list[str] = []
    role_classes = subclasses_of(og, URIRef(GFO_LIGHT + "Role"))
    seeded_roles = {s for s in pg.subjects(RDF.type, None)
                    if isinstance(s, URIRef) and set(pg.objects(s, RDF.type)) & role_classes}
    seeded = {str(s) for s in seeded_roles}

    seen_classes: dict[URIRef, set] = {}
    for g in snapshots:
        for s in sorted({x for x in g.subjects(RDF.type, None) if isinstance(x, URIRef)}):
            types = {t for t in g.objects(s, RDF.type)
                     if isinstance(t, URIRef) and (t in role_classes
                                                  or str(t).startswith(PH))}
            if not types:
                continue
            prev = seen_classes.get(s)
            if prev is None:
                seen_classes[s] = types
            elif prev != types:
                added = ", ".join(sorted(str(t).rsplit("/", 1)[-1] for t in types - prev))
                gone = ", ".join(sorted(str(t).rsplit("/", 1)[-1] for t in prev - types))
                errors.append(
                    f"retype: <{s}> changed its declared class between graphs "
                    f"(gained {added or 'nothing'}, lost {gone or 'nothing'}). A "
                    f"meaning is a relation, not a change of type, so a class that "
                    f"moves with a process's progress leaves the graph unreadable "
                    f"at a fixed point."
                )
                seen_classes[s] = types

        for s in sorted({x for x in g.subjects(RDF.type, None) if isinstance(x, URIRef)}):
            roles = {t for t in g.objects(s, RDF.type)
                     if isinstance(t, URIRef) and t in role_classes}
            if not roles or str(s) in seeded:
                continue
            contexts = list(g.objects(s, URIRef(PH + "roleIn")))
            holders = list(g.objects(s, URIRef(PH + "playedBy")))
            if not contexts:
                errors.append(
                    f"role: <{s}> is a Role the oracle minted but relates no "
                    f"ph:roleIn, so the situation it is played in is unreadable."
                )
            if not holders:
                errors.append(
                    f"role: <{s}> is a Role the oracle minted but relates no "
                    f"ph:playedBy, so who holds it is unreadable."
                )
            for role in roles:
                ctxs = [str(o) for o in contexts]
                if len(ctxs) != len(set(ctxs)):
                    errors.append(
                        f"role: <{s}> holds a role twice in one situation, so the "
                        f"same meaning appears more than once for one holder."
                    )
    return errors



def copy_graph(src: Graph) -> Graph:
    """A detached copy. `Graph() | other` does not copy in this rdflib --
    `|` mutates the left operand and the result came back empty, so every
    snapshot taken that way was empty and every count taken from it was zero. """
    out = Graph()
    for triple in src:
        out.add(triple)
    return out


def walk_law(case: Path, limit: int = 60) -> tuple[list[dict], list[Graph], list[str]]:
    """Play a law forward, stepping the clock through its own calendar.

    A walk that never moves the clock reaches four acts of an election law:
    `announce` and a nomination each, because every duty due on a later day is
    simply not in the verdict yet. That is the whole law's later half --
    preparing, voting, counting, proclaiming, repeating -- silently untested by
    every check built on it. So the clock is stepped through the moments the
    law DECLARES on its ph:CalendarPoints, which the framework says is how a
    consumer finds where a law is, and whatever is offered is applied at each.

    Returns one record per accepted act, carrying everything the judges below
    need, so one walk serves them all and each reports under its own name.
    """
    client, errs = _client(case)
    if client is None:
        return [], [], errs

    from runtime.oracle import OracleRejected, UndeclaredSubject
    from runtime.lawdriver import calendar_moments

    manifest, merrs = _manifest_of(case)
    if merrs:
        return [], [], merrs
    by_id = {e.get("id"): e for e in manifest.get("ecas", [])}

    def values(g):
        return {(s, pr): o for s, pr, o in g}

    def clock_of(g):
        ck = URIRef(PH + "clock/now")
        d = g.value(ck, URIRef(PH + "dayIndex"))
        h = g.value(ck, URIRef(PH + "atHour"))
        return (str(d) if d is not None else None,
                str(h) if h is not None else None)

    def class_counts(g):
        # Named, not `_`: binding `_` twice in one unpack makes the second
        # name the PREDICATE, so this counted rdf:type instead of the class and
        # every count came out empty.
        out = {}
        for _subj, _pred, obj in g.triples((None, RDF.type, None)):
            if isinstance(obj, URIRef) and str(obj).startswith(PH):
                out[obj] = out.get(obj, 0) + 1
        return out

    steps = []
    snapshots = [copy_graph(client.graph)]
    plan = [None] + calendar_moments(client) + [(10 ** 6, 10)]
    for moment in plan:
        if moment is not None:
            client.set_clock(*moment)
        for _ in range(limit):
            moved = False
            before_counts = class_counts(client.graph)
            before_values = values(client.graph)
            sent_clock = clock_of(client.graph)
            for act in pending_acts(client, by_id):
                name = act.get("eca")
                entry = by_id.get(name) or {}
                try:
                    client.apply(act)
                except OracleRejected:
                    continue
                except UndeclaredSubject as e:
                    # The oracle returned a graph carrying an individual typed by
                    # a class this ontology does not declare. That is a REPORT
                    # about the artefact set, not a crash of the gate: it is what
                    # `check_population` exists to say, and it used to be
                    # unreachable because the walk runs first and died here with
                    # a traceback instead. Reported under the walk's own name so
                    # the diagnostic survives to be read.
                    errors.append(
                        f"walk: `{name}` returned an individual typed by a class "
                        f"the ontology does not declare, so the set is not "
                        f"reviewable: {e}"
                    )
                    break
                snap = copy_graph(client.graph)
                snapshots.append(snap)
                cur = values(snap)
                rewritten = {
                    "ph:" + str(pr)[len(PH):]
                    for (s, pr), o in cur.items()
                    if (s, pr) in before_values and before_values[(s, pr)] != o
                    and isinstance(pr, URIRef) and str(pr).startswith(PH)
                }
                steps.append({
                    "eca": name,
                    "mints": entry.get("mints"),
                    "inputs": entry.get("inputs"),
                    "sent_clock": sent_clock,
                    "got_clock": clock_of(snap),
                    "before_counts": before_counts,
                    "after_counts": class_counts(snap),
                    "rewritten": rewritten,
                })
                moved = True
                break
            if not moved:
                break

    if not steps:
        return [], [], ["walk: no act could be applied from the seeded graph, so "
                        "the checks built on this walk proved nothing"]
    if len(steps) < 4:
        return steps, snapshots, [f"walk: only {len(steps)} act(s) were "
                                  f"reachable, too few to exercise a law; the "
                                  f"clock is probably not reaching its later "
                                  f"phases"]
    return steps, snapshots, []


def check_reencoding(og, steps, snapshots):
    """5.2 and 5.3: declarations match the re-encoding, and it is stable."""
    written = set()
    for step in steps:
        written |= step["rewritten"]
    return (check_reencoded_are_functional(og, written)
            + check_no_accumulation(og, snapshots))


def check_totality(case: Path, steps):
    """5.6: nothing a verdict names may be absent from the graph."""
    client, errs = _client(case)
    if client is None:
        return errs
    manifest, merrs = _manifest_of(case)
    if merrs:
        return merrs
    by_id = {e.get("id"): e for e in manifest.get("ecas", [])}
    creating = {eid for eid, e in by_id.items() if e.get("mints")}

    errors = []
    from runtime.oracle import OracleRejected
    for _ in range(60):
        moved = False
        for act in pending_acts(client, by_id):
            try:
                client.apply(act)
            except OracleRejected:
                continue
            try:
                errors += check_verdict_is_total(
                    client, client.check(), act.get("eca"), creating)
            except Exception as e:  # noqa: BLE001
                errors.append(f"totality: `check` failed after "
                              f"`{act.get('eca')}`: {e}")
            moved = True
            break
        if not moved:
            break
    return errors


def check_collisions(steps):
    """5.4: an act that declares `mints` must really mint."""
    errors = []
    for step in steps:
        minted = step.get("mints")
        if not minted:
            continue
        before = step["before_counts"].get(URIRef(PH + minted), 0)
        after = step["after_counts"].get(URIRef(PH + minted), 0)
        if after <= before:
            errors.append(
                f"collision: `{step['eca']}` declares mints: {minted}, but "
                f"accepting it did not add an individual of that class (count "
                f"stayed {before}). A minted IRI must include every dimension "
                f"along which the fact repeats, or two occurrences collide and "
                f"one individual comes to encode two histories."
            )
    return errors


def check_clock_untouched(steps):
    """5.5: `apply` returns the clock it was sent."""
    return [
        f"clock: `{s['eca']}` returned ph:Clock {s['got_clock']} but the driver "
        f"sent {s['sent_clock']}. The runtime is the clock's only writer, so an "
        f"act must neither move nor erase it."
        for s in steps if s["got_clock"] != s["sent_clock"]
    ]


def check_transformation_inputs(og: Graph, steps: list[dict]) -> list[str]:
    """5.9: an act must not conjure a physical thing.

    Reported, not failed: every shipped law predates the requirement, and the
    point of reporting is to name the act so the rewrite has a target.

    Narrowed to PHYSICAL classes after the first version flagged 93 things. It
    treated any class that grew as unaccounted, which caught the real defect --
    `prepare` conjuring nine `ph:BallotVote` papers -- and drowned it in the
    legitimate minting that is the transformation mechanism itself: every Role a
    citizen takes on, and every occurrence of a phase, is *supposed* to appear
    when the act happens.

    So the legitimate cases are excluded by what the law DECLARES, not by a
    list: a `gfo-light:Role` subclass is a meaning, and an occurrence of a
    declared phase is what the framework calls an instance of its phase. What is
    left is a class that is neither -- a physical thing appearing with nothing to
    be it made from, which is what the requirement forbids.
    """
    legitimate = subclasses_of(og, URIRef(GFO_LIGHT + "Role"))
    legitimate |= set(reachable_phases(og))

    errors = []
    for step in steps:
        grew = {
            cls[len(PH):]: (step["before_counts"].get(cls, 0),
                            step["after_counts"][cls])
            for cls in step["after_counts"]
            if step["after_counts"][cls] > step["before_counts"].get(cls, 0)
        }
        explained = {step["mints"]} | {
            i for i in (step.get("inputs") or []) if isinstance(i, str)
        }
        explained = {e[len(PH):] if str(e).startswith(PH) else e for e in explained}
        for cls, (before, after) in sorted(grew.items()):
            if cls in explained:
                continue
            if URIRef(PH + cls) in legitimate:
                continue
            errors.append(
                f"transformation: `{step['eca']}` brought {after - before} new "
                f"ph:{cls} individual(s) into existence, and it is neither a Role "
                f"the individual takes on nor an occurrence of a declared phase, "
                f"so nothing accounts for it appearing. A citizen's act may give "
                f"an existing thing a new meaning; it may not create a physical "
                f"one out of nothing. (Reported, not failed: every shipped law "
                f"predates the requirement.)"
            )
    return errors


def check_local_redeclaration(og: Graph, sg: Graph | None) -> list[str]:
    """A concept declared in both the law and the shared file (REPORTED).

    Two declarations of one concept is the failure the shared vocabulary
    exists to prevent: two laws' mailboxes would be unrelated, and two ways
    of writing on a thing would be two ways of saying the same thing. Naming
    both is enough -- a reviewer can see which is which and what a subject
    resolves to.

    `og` is the law's own declarations and `sg` the shared file, kept
    separate on purpose. Referring to a shared class is not declaring it:
    writing `ph:CreateBallots ph:hasParticipant ph:Mailbox` uses the concept
    without restating it, and only a class the law gives its own
    `rdfs:subClassOf` counts as a redeclaration.

    Reported rather than failed on purpose. Every shipped law declared these
    locally before the shared file existed, so failing here would block the
    migration behind the change whose entire point is that they migrate to
    it. It becomes a failure once they have.
    """
    if sg is None:
        return []
    shared = {str(c) for c in declared_classes(sg)} | {
        str(p) for p in declared_properties(sg)
    }
    own = {str(c) for c in declared_classes(og)} | {
        str(p) for p in declared_properties(og)
    }

    notes: list[str] = []
    for name in sorted(shared & own):
        short = name.rsplit("/", 1)[-1]
        in_sg = sorted(str(s).rsplit("/", 1)[-1]
                       for s in gfo_superclasses(sg, URIRef(name)))
        in_og = sorted(str(s).rsplit("/", 1)[-1]
                       for s in gfo_superclasses(og, URIRef(name)))
        differs = "" if in_sg == in_og else (
            f" The two do not even agree: shared grounds it under "
            f"{', '.join(in_sg)} and the law under {', '.join(in_og)}, so which "
            f"one a subject resolves through depends on which file a consumer "
            f"happens to read."
        )
        notes.append(
            f"local redeclaration: ph:{short} is declared in "
            f"framework/physical.ttl and restated in ontology.ttl. Two "
            f"declarations of one concept leave two laws' versions unrelated; "
            f"declare it once, in the shared file, and draw it here."
            f"{differs}"
        )
    return notes


def check_world_restatement(own_pg: Graph | None,
                            wg: Graph | None) -> list[str]:
    """A world-owned individual restated in a case's own seeds (REFUSED).

    Reference-don't-restate extended to individuals: a law names Alice, it
    never declares her. Unlike class-level local redeclaration (reported,
    because shipped laws predated the shared file), restatement here is a
    refusal: two subject-blocks for one IRI put two states on one thing in
    the merged graph — two labels, two clock readings — which no consumer
    can resolve. Only subjects count: naming a world IRI as an object (a
    Role `playedBy` a citizen) is reference, not restatement.
    """
    if own_pg is None or wg is None:
        return []
    world_owned = {s for s in wg.subjects() if isinstance(s, URIRef)}
    errors: list[str] = []
    for subj in sorted({s for s in own_pg.subjects()
                        if isinstance(s, URIRef) and s in world_owned},
                       key=str):
        errors.append(
            f"world restatement: <{subj}> is declared in the shared world "
            f"and restated in this case's seeds. Two declarations of one "
            f"individual leave two states for one thing; reference it by "
            f"IRI and delete the local block."
        )
    return errors


def capability_classes(og: Graph) -> set[URIRef]:
    """The shared classes that qualify an object rather than name one.

    DIRECT subclasses of ph:PhysicalCapability, deliberately not all of them.
    The hierarchy says a Mailbox is a Container and a Sheet is Inscribable,
    so the whole subtree below the root is every object that *bears* a
    capability -- which is most of the physical vocabulary and none of the
    capabilities. The qualifications themselves are the kinds directly under
    the root, and one of those being a direct subclass is what makes a new
    capability need no code change here.
    """
    root = URIRef(PH + "PhysicalCapability")
    if root not in declared_classes(og):
        return set()
    return {s for s in og.subjects(RDFS.subClassOf, root)
            if isinstance(s, URIRef) and s != root}


def check_instrument_narrowing(case: Path, sg: Graph | None) -> list[str]:
    """An act that qualifies by a NAMED KIND, where a capability would do (REPORTED).

    The law-extraction rule is that text leaving the instrument open leaves it
    open: `mayor-quorum/law.txt:11-12` says to "make the ballot votes" and have
    people "write their name", and never names what to write with. An act
    requiring `ph:Inscriptible` is satisfied by a hamlet stocked with pencils
    and one stocked with pens; an act requiring a named kind of instrument has
    quietly resolved the law's vagueness in the artefacts, where the law left
    it for the world.

    The gate cannot read the law text to know whether it named one, so this
    names the narrowing for review rather than judging it. That is the honest
    division: deciding which of the two a text did is a reading, and the
    framework has no business making readings.
    """
    if sg is None:
        return []
    manifest, errs = _manifest_of(case)
    if errs:
        return []
    og, oerrs = parse(case / "ontology.ttl")
    if og is None:
        return []
    for triple in sg:
        og.add(triple)
    caps = capability_classes(og)
    shared_kinds = {str(c) for c in declared_classes(sg)} - {str(c) for c in caps}

    notes: list[str] = []
    for e in manifest.get("ecas", []) or []:
        for req in e.get("requires") or []:
            name = req.get("class") or req.get("kind")
            if not name:
                continue
            # Manifests name classes bare (`mints: MayorElectionCycle`), but a
            # prefixed or absolute IRI is not a mistake worth failing on, so
            # all three spellings resolve to the same class.
            text = str(name)
            if text.startswith(PH):
                iri = URIRef(text)
            elif text.startswith("http"):
                iri = URIRef(text)
            else:
                iri = URIRef(PH + text.removeprefix("ph:"))
            if str(iri) in caps or str(iri) not in shared_kinds:
                continue
            notes.append(
                f"instrument narrowing: eca '{e.get('id')}' requires "
                f"{str(iri).rsplit('/', 1)[-1]} by named kind. Check whether "
                f"{case.name}/law.txt names it; if the text left the choice "
                f"open, qualify by the capability instead (anything under "
                f"ph:PhysicalCapability), so a hamlet stocking a different such "
                f"object is not blocked by a class the law never mentioned."
            )
    return notes


def check_lean(case: Path) -> list[str]:

    lean = case / "rules.lean"
    try:
        proc = subprocess.run(
            ["lake", "env", "lean", str(lean)],
            cwd=ROOT / "lean",
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        return ["rules.lean: `lake` not found on PATH"]
    except subprocess.TimeoutExpired:
        return ["rules.lean: lean check timed out after 300s"]
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        return [f"rules.lean: lean failed (exit {proc.returncode}):\n{detail}"]
    return []


def check_manifest(case: Path, og: Graph | None) -> list[str]:
    errors: list[str] = []
    mf = case / "manifest.yaml"
    try:
        data = yaml.safe_load(mf.read_text())
    except Exception as e:  # noqa: BLE001
        return [f"manifest.yaml: YAML parse failed: {e}"]
    ecas = data.get("ecas", [])
    ids = [e.get("id") for e in ecas]
    if len(ids) != len(set(ids)):
        errors.append("manifest.yaml: duplicate eca ids")

    ph_classes = declared_classes(og) if og is not None else set()
    for e in ecas:
        proc = e.get("eca_process", "")
        if expand(f"ph:{proc}") not in ph_classes:
            errors.append(
                f"manifest.yaml: eca '{e.get('id')}' process '{proc}' is not a ph: "
                f"class declared in ontology.ttl"
            )
        if e.get("modality") not in {"should", "must", "may"}:
            errors.append(
                f"manifest.yaml: eca '{e.get('id')}' has bad modality {e.get('modality')!r}"
            )
        if "holder_role" not in e:
            errors.append(
                f"manifest.yaml: eca '{e.get('id')}' declares no holder_role, so no "
                f"consumer knows which Role the duty attaches to"
            )
        minted = e.get("mints")
        if minted is not None and expand(f"ph:{minted}") not in declared_classes(og):
            errors.append(
                f"manifest.yaml: eca '{e.get('id')}' declares it mints "
                f"'{minted}', which ontology.ttl does not declare as a class"
            )
        elif minted is not None and expand(f"ph:{minted}") not in process_classes(og):
            errors.append(
                f"manifest.yaml: eca '{e.get('id')}' declares it mints "
                f"'{minted}', which is not a gfo-core:Process"
            )
        # `acts_on`, never `on`: YAML 1.1 resolves a bare `on` key to the boolean
        # True, so `e.get("on")` is silently None and this loop never runs -- a
        # check that reads as correct and checks nothing. Found by mutating the
        # declared class to one the ontology lacks and watching the gate pass.
        for target in e.get("acts_on") or []:
            name = target.get("class") if isinstance(target, dict) else target
            if not name:
                errors.append(
                    f"manifest.yaml: eca '{e.get('id')}' has an entry in "
                    f"`acts_on` that names no class, so nothing says what the "
                    f"duty acts on"
                )
                continue
            text = str(name)
            iri = URIRef(text) if text.startswith("http") else expand(f"ph:{text.removeprefix('ph:')}")
            if iri in declared_classes(og):
                continue
            errors.append(
                f"manifest.yaml: eca '{e.get('id')}' declares it acts on "
                f"'{text}', which ontology.ttl does not declare as a class -- so "
                f"the world cannot contain one and `apply` would refuse the act "
                f"unconditionally"
            )
        if "params" not in e:
            errors.append(
                f"manifest.yaml: eca '{e.get('id')}' declares no params, so no "
                f"consumer knows how to build a complete act"
            )
    return errors


def run(case: Path, schema_only: bool) -> tuple[list[tuple[str, list[str]]], list[str], list[tuple[str, list[str]]]]:
    results: list[tuple[str, list[str]]] = []
    notes: list[tuple[str, list[str]]] = []
    all_errors: list[str] = []

    def record(name: str, errs: list[str]) -> None:
        results.append((name, errs))
        all_errors.extend(errs)

    def attempt(name: str, fn, *a, **kw) -> None:
        """Run one check, turning a crash into a reported failure.

        A malformed artefact set must not take the gate down with it. Several
        checks drive the oracle, and the client's own validation refuses a graph
        carrying an individual typed by a class the ontology does not declare --
        which is exactly what a set with an undeclared seeded type is. That
        surfaced as a traceback out of `check.py` rather than as a diagnostic, and
        `freeze.py` runs the gate first, so the caller saw an opaque crash
        instead of the finding. One guard here covers every check that drives the
        oracle, including ones added later, which is why it is here rather than
        wrapped around the three call sites that happened to need it.
        """
        try:
            record(name, fn(*a, **kw))
        except Exception as e:  # noqa: BLE001 - the point is to survive anything
            record(name, [f"{name}: the check could not complete on this artefact "
                          f"set: {type(e).__name__}: {e}"])

    def report(name: str, msgs: list[str]) -> None:
        """A finding that must be named but does not make the set unreviewable.

        Distinct from `record` because some findings are ahead of the laws they
        apply to. A law predating a requirement is not thereby broken, and
        refusing to load it would block the work that fixes it behind the
        requirement's arrival.
        """
        if msgs:
            notes.append((name, msgs))

    og, errs = parse(case / "ontology.ttl")
    record("ontology parse", errs)
    pg, perrs = parse(case / "population.ttl")
    record("population parse", perrs)

    # Every ontology check downstream takes the MERGED graph: the law's own
    # declarations plus the shared vocabulary. Nothing downstream changes
    # shape, because each was already asking whether a subject's type is
    # declared somewhere the law can reach, and the shared file is somewhere
    # the law can reach. Merging is what makes "available" cost no
    # exemption rather than needing one carved out per check.
    sg, serrs = parse_shared()
    record("shared vocabulary parse", serrs)
    if og is not None and sg is not None:
        og = copy_graph(og)
        for _s, _p, o in sg:
            og.add((_s, _p, o))

    # Every population check downstream takes the MERGED seed graph: the
    # law's own seeds plus the shared world. Duplicates are harmless (a
    # graph is a set), which is what lets per-case populations shrink into
    # law-seeds-only without changing what any check judges. Nothing about
    # the law's own declarations changes: `own_classes` below still scopes
    # coherence to what the law declares.
    wg, werrs = parse_world()
    record("world parse", werrs)
    # The law's own seeds, kept separate from the merged graph: seed parity
    # judges what the LAW seeds (available-not-required means world furniture
    # a law never names is present, not duplicated), while every other
    # population check judges the merged graph the simulation runs.
    own_pg = pg
    if pg is not None and wg is not None:
        pg = copy_graph(pg)
        for _s, _p, o in wg:
            pg.add((_s, _p, o))

    if og is not None:
        # The law's own declared classes, kept separate from the merged graph:
        # "available, not required" means the law's coherence is judged on what
        # the law declares, not on whether it draws on every shared class.
        own_og, _ = parse(case / "ontology.ttl")
        own_classes = declared_classes(own_og) if own_og is not None else None
        record("framework invariants", check_framework_invariants(og))
        record("grounding", check_grounding(og))
        record("frozen TBox", check_tbox(og))
        record("phase hierarchy", check_phase_reachability(og, own_classes))
        report("local redeclaration", check_local_redeclaration(own_og or og, sg))
        report("instrument narrowing", check_instrument_narrowing(case, sg))
        try:
            manifest = yaml.safe_load((case / "manifest.yaml").read_text())
        except Exception:  # noqa: BLE001 - reported by the manifest check
            manifest = None
        record("orphan processes",
               check_no_orphan_process(og, pg or Graph(), manifest, own_classes))
        if not schema_only:
            attempt("manifest vs oracle", check_manifest_against_oracle, case, og)
            attempt("clock totality", check_clock_totality, case)
            attempt("clock monotonicity", check_clock_monotonicity, case)
            record("readings declared", check_reading_declarations(case, og))
            attempt("graph round trip", check_graph_roundtrip, case)
            # One walk, several judges, each reported under its own name so a
            # failure says which property broke rather than "materialisation".
            try:
                steps, snaps, werrs = walk_law(case)
            except Exception as e:  # noqa: BLE001 - see `attempt`
                # The walk drives the oracle, so it meets the same malformed-set
                # refusal every other driving check does. Reported as the walk's
                # own finding: the judges built on it have nothing to judge.
                steps, snaps, werrs = [], [], [
                    f"walk: the walk could not complete on this artefact set: "
                    f"{type(e).__name__}: {e}"]
            attempt("role shape", check_role_shape, og, pg, snaps)
            if werrs:
                record("walk", werrs)
            else:
                attempt("re-encoding is declared and stable",
                        check_reencoding, og, steps, snaps)
                attempt("totality of the verdict", check_totality, case, steps)
                attempt("minted IRI freshness", check_collisions, steps)
                attempt("clock untouched by apply", check_clock_untouched, steps)
                attempt("transformation inputs", check_transformation_inputs, og, steps)
            # Reads the same `snaps` the walk just produced. Previously it was
            # handed a module-level RUNTIME_GRAPHS that nothing ever appended to,
            # so it always received an empty list and always reported "no runtime
            # graph was available" -- the check had never once run.
            record("chronoid shape", check_chronoid_shape(og, snaps))
    if pg is not None and og is not None:
        record("population", check_population(pg, og))
        record("positions are moments", check_positions_are_moments(pg, og))

        record("seed parity", check_seed_parity(case, own_pg or pg))
        record("world restatement", check_world_restatement(own_pg, wg))
        record("calendar spans", check_phase_calendar_spans(og, pg))
        record("phase ordering", check_no_phase_ordering(og, pg))
        record("causedBy direction", check_caused_by(og, pg))
    record("manifest", check_manifest(case, og))

    if not schema_only:
        record("rules.lean", check_lean(case))

    return results, all_errors, notes


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--schema-only"]
    schema_only = "--schema-only" in argv[1:]
    if not args:
        print(__doc__)
        return 2
    case = (ROOT / args[0]).resolve()
    results, all_errors, notes = run(case, schema_only)
    for name, errs in results:
        if errs:
            print(f"--- {name}: FAIL ---")
            for e in errs:
                print(f"  {e}")
        else:
            print(f"--- {name}: ok ---")
    for name, msgs in notes:
        print(f"--- {name}: REPORTED ---")
        for m in msgs:
            print(f"  {m}")
    if all_errors:
        print(f"\n{len(all_errors)} problem(s): set unreviewable until fixed.")
        return 1
    if notes:
        print("\nall checks pass, with findings reported above for review.")
        return 0
    print("\nall checks pass: set may proceed to the review gate (tools/lawgen/freeze.py).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
