"""Machine checks for a law artefact set: the review gate.

Usage:
  uv run python scripts/check.py artefacts/mayor-2027
  uv run python scripts/check.py --schema-only artefacts/mayor-2027

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

Runtime checks (need a compiled oracle; see scripts/test_oracle.py):
  clock totality, graph round trip.

On failure the harness reports diagnostics and marks the set unreviewable
until regenerated or fixed (spec: Machine checks before human review).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lawdriver import act_from_declaration, play_forward  # noqa: E402

import yaml
from rdflib import OWL, RDF, RDFS, Graph, Namespace, URIRef

ROOT = Path(__file__).resolve().parent.parent
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


def check_tbox(g: Graph) -> list[str]:
    """The ontology is a frozen schema: classes only, no individuals."""
    errors: list[str] = []
    classes = declared_classes(g)
    props = declared_properties(g)

    # Every ph: class has a GFO-light/GFO-core superclass.
    for c in sorted(classes, key=str):
        if not str(c).startswith(PH):
            continue
        supers = values_of(g, c, RDFS.subClassOf)
        if not any(str(s).startswith((GFO_LIGHT, GFO_CORE)) for s in supers):
            errors.append(f"ontology.ttl: class <{c}> lacks a GFO-light/GFO-core superclass")

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


def check_phase_reachability(g: Graph) -> list[str]:
    """Every Process class reachable from a root through ph:hasPhase (6.4)."""
    procs = process_classes(g)
    reached = reachable_phases(g)
    containers, _ = phase_graph(g)
    errors: list[str] = []
    for c in sorted(procs - reached - containers, key=str):
        errors.append(
            f"phase hierarchy: <{c}> is a gfo-core:Process that no declared root "
            f"reaches through ph:hasPhase. A consumer reads the hierarchy to know "
            f"what the law is made of; an unreachable class is in neither."
        )
    return errors


def check_no_orphan_process(
    g: Graph, pg: Graph, manifest: dict | None
) -> list[str]:
    """No Process class is referenced by nothing at all (6.5).

    A declared Process class is live if something in the artefact set can
    reach it: another Process contains it through ph:hasPhase, the manifest
    names it as an ECA's process, or the seeded graph has an individual typed
    with it. Reachability alone cannot tell a real root from a stray one —
    both are Processes that contain nothing and are contained by nothing — so
    the seeded individual is what settles it.
    """
    procs = process_classes(g)
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
    live = phases | named | minted | instantiated

    errors: list[str] = []
    for c in sorted(procs - live, key=str):
        errors.append(
            f"orphan Process class: <{c}> is declared but nothing in the law reaches "
            f"it — no root contains it through ph:hasPhase, no manifest eca_process "
            f"names it, and the seeded graph has no individual typed with it. Declare "
            f"it as a phase of a Process, name it in the manifest, or delete it."
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
            f"cross-validated against `oracle list`. Run scripts/build_oracle.py first."
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
    sys.path.insert(0, str(ROOT / "src"))
    from potato_hamlet.oracle import OracleClient

    try:
        return OracleClient(case), None
    except FileNotFoundError as e:
        return None, [str(e)]


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
        client.set_time(day, hour)
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
                from potato_hamlet.oracle import OracleRejected

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
    from potato_hamlet.oracle import OracleClient

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

    from potato_hamlet.oracle import OracleRejected, UndeclaredSubject

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


def check_lean(case: Path) -> list[str]:

    lean = case / "rules.lean"
    try:
        proc = subprocess.run(
            ["lake", "env", "lean", str(lean)],
            cwd=ROOT / "potato-hamlet-lean",
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
        if "params" not in e:
            errors.append(
                f"manifest.yaml: eca '{e.get('id')}' declares no params, so no "
                f"consumer knows how to build a complete act"
            )
    return errors


def run(case: Path, schema_only: bool) -> tuple[list[tuple[str, list[str]]], list[str]]:
    results: list[tuple[str, list[str]]] = []
    all_errors: list[str] = []

    def record(name: str, errs: list[str]) -> None:
        results.append((name, errs))
        all_errors.extend(errs)

    og, errs = parse(case / "ontology.ttl")
    record("ontology parse", errs)
    pg, perrs = parse(case / "population.ttl")
    record("population parse", perrs)

    if og is not None:
        record("framework invariants", check_framework_invariants(og))
        record("grounding", check_grounding(og))
        record("frozen TBox", check_tbox(og))
        record("phase hierarchy", check_phase_reachability(og))
        try:
            manifest = yaml.safe_load((case / "manifest.yaml").read_text())
        except Exception:  # noqa: BLE001 - reported by the manifest check
            manifest = None
        record("orphan processes", check_no_orphan_process(og, pg or Graph(), manifest))
        if not schema_only:
            record("manifest vs oracle", check_manifest_against_oracle(case, og))
            record("clock totality", check_clock_totality(case))
            record("readings declared", check_reading_declarations(case, og))
            record("graph round trip", check_graph_roundtrip(case))
    if pg is not None and og is not None:
        record("population", check_population(pg, og))
        record("calendar spans", check_phase_calendar_spans(og, pg))
        record("phase ordering", check_no_phase_ordering(og, pg))
        record("causedBy direction", check_caused_by(og, pg))
    record("manifest", check_manifest(case, og))

    if not schema_only:
        record("rules.lean", check_lean(case))

    return results, all_errors


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--schema-only"]
    schema_only = "--schema-only" in argv[1:]
    if not args:
        print(__doc__)
        return 2
    case = (ROOT / args[0]).resolve()
    results, all_errors = run(case, schema_only)
    for name, errs in results:
        if errs:
            print(f"--- {name}: FAIL ---")
            for e in errs:
                print(f"  {e}")
        else:
            print(f"--- {name}: ok ---")
    if all_errors:
        print(f"\n{len(all_errors)} problem(s): set unreviewable until fixed.")
        return 1
    print("\nall checks pass: set may proceed to the review gate (scripts/freeze.py).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
