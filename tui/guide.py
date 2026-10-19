"""Display-layer derivations for the generic TUI guide.

Pure functions over three deliberately separate sources:

- structure from the declared ``ph:hasPhase`` hierarchy (schema),
- schedule from calendar bounds (seed/runtime graph),
- currency from the Lean verdict (``check`` output),
- history from the knowledge graph.

The guide derives no phase, no authority rule, and no readiness of its
own. It displays the oracle's ``phase`` reading verbatim and surfaces a
declared-window/oracle-phase disagreement as a warning rather than
resolving it.

No law-specific code: every widget is built from the manifest's declared
``holder_role``, parameters (``selected``/``choices``), modality, labels,
messages, and reading templates.
"""

from __future__ import annotations

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

PH = "https://potato-hamlet.example/ontology/"
_RDF_TYPE = RDF.type
_GFO_CHRONOID = URIRef("https://w3id.org/gfo-light/Chronoid")


def _ph(local: str) -> URIRef:
    return URIRef(PH + local)


def _short(iri: str) -> str:
    return iri.rsplit("/", 1)[-1]


# -- structure -----------------------------------------------------------

def process_roots(schema: Graph) -> list[str]:
    """Process classes that are never a phase of another (the roots)."""
    phases = {str(o) for _, o in schema.subject_objects(_ph("hasPhase"))}
    subjects = {str(s) for s, _ in schema.subject_objects(_ph("hasPhase"))}
    return sorted(subjects - phases)


def process_children(schema: Graph, process_class: str) -> list[str]:
    """Phases declared via ``ph:hasPhase`` for a Process class."""
    return sorted(
        {str(o) for o in schema.objects(URIRef(process_class), _ph("hasPhase"))}
    )


def process_tree(schema: Graph) -> dict[str, list[str]]:
    """The declared hierarchy: root class IRI -> ordered phase class IRIs."""
    return {root: process_children(schema, root) for root in process_roots(schema)}


# -- schedule ------------------------------------------------------------

def _literal(graph: Graph, subject, predicate: URIRef):
    value = graph.value(subject, predicate)
    return None if value is None else str(value)


def _point_info(graph: Graph, point) -> dict:
    return {
        "iri": str(point),
        "label": _literal(graph, point, _ph("label")),
        "atDate": _literal(graph, point, _ph("atDate")),
        "dayIndex": _literal(graph, point, _ph("dayIndex")),
        "atHour": _literal(graph, point, _ph("atHour")),
        "marksPhase": sorted(str(m) for m in graph.objects(point, _ph("marksPhase"))),
    }


def phase_windows(graph: Graph) -> dict[str, list[dict]]:
    """Windows per phase class IRI, read from the artefacts, never computed.

    Two shapes: a ``CalendarSpan`` carrying ``marksPhase`` (bounded by
    ``temporallyStartedBy``/``temporallyFinishedBy`` points, or relative
    via ``gapDays``), and a ``CalendarPoint`` directly carrying
    ``marksPhase`` (a point window).
    """
    out: dict[str, list[dict]] = {}
    for span in graph.subjects(_RDF_TYPE, _ph("CalendarSpan")):
        for phase in graph.objects(span, _ph("marksPhase")):
            start = graph.value(span, URIRef(PH + "temporallyStartedBy"))
            finish = graph.value(span, URIRef(PH + "temporallyFinishedBy"))
            # Predicates may live under gfo-core namespace; fall back by scan.
            if start is None or finish is None:
                for p, o in graph.predicate_objects(span):
                    name = str(p).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
                    if name == "temporallyStartedBy" and start is None:
                        start = o
                    elif name == "temporallyFinishedBy" and finish is None:
                        finish = o
            entry = {
                "kind": "span",
                "iri": str(span),
                "label": _literal(graph, span, _ph("label")),
                "gapDays": _literal(graph, span, _ph("gapDays")),
                "start": _point_info(graph, start) if start is not None else None,
                "finish": _point_info(graph, finish) if finish is not None else None,
            }
            out.setdefault(str(phase), []).append(entry)
    for point in graph.subjects(_RDF_TYPE, _ph("CalendarPoint")):
        for phase in graph.objects(point, _ph("marksPhase")):
            entry = {"kind": "point", "point": _point_info(graph, point)}
            out.setdefault(str(phase), []).append(entry)
    return out


def window_summary(windows: dict[str, list[dict]]) -> dict[str, str]:
    """One human line per phase: 'label (day 0–9)' or date forms, read only."""

    def day_of(point: dict | None) -> str:
        if not point:
            return "?"
        day, hour, date = point.get("dayIndex"), point.get("atHour"), point.get("atDate")
        if day is None:
            return "?"
        text = f"day {day}"
        if hour is not None:
            text += f"@{hour}h"
        if date:
            text += f" {date}"
        return text

    summaries = {}
    for phase, entries in windows.items():
        parts = []
        for entry in entries:
            if entry["kind"] == "span":
                if entry.get("gapDays") is not None:
                    parts.append(f"{entry.get('label') or 'span'} (+{entry['gapDays']}d relative)")
                else:
                    parts.append(
                        f"{entry.get('label') or 'span'} "
                        f"({day_of(entry.get('start'))}–{day_of(entry.get('finish'))})"
                    )
            else:
                point = entry["point"]
                parts.append(f"{point.get('label') or 'point'} ({day_of(point)})")
        summaries[phase] = "; ".join(parts) if parts else "unscheduled"
    return summaries


# -- instances -----------------------------------------------------------

def _chronoid_bounds(graph: Graph, instance: str) -> tuple[object, object, object]:
    chrono = graph.value(URIRef(instance), _ph("hasTime"))
    if chrono is None:
        return None, None, None
    start = finish = None
    for p, o in graph.predicate_objects(chrono):
        name = str(p).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        if name == "temporallyStartedBy" and start is None:
            start = o
        elif name == "temporallyFinishedBy" and finish is None:
            finish = o
    return chrono, start, finish


def process_classes(schema: Graph) -> set[str]:
    """Every Process class reachable from a root through ``ph:hasPhase``."""
    tree = process_tree(schema)
    classes = set(tree)
    stack = list(tree.values())
    while stack:
        for phase in stack.pop():
            if phase not in classes:
                classes.add(phase)
                stack.append(process_children(schema, phase))
    return classes


def instance_status(graph: Graph, schema: Graph) -> list[dict]:
    """Every process instance: initialised | ongoing | finished-with-outcome.

    - initialised: no start bound on its Chronoid (awaiting its trigger);
    - finished: a finish bound (plus ``ph:outcome`` where the law records one);
    - ongoing: started and not finished.
    """
    classes = process_classes(schema)
    seen: dict[str, str] = {}
    for cls in classes:
        for subject in graph.subjects(_RDF_TYPE, URIRef(cls)):
            if isinstance(subject, URIRef):
                seen.setdefault(str(subject), cls)
    out = []
    for iri in sorted(seen):
        cls = seen[iri]
        _, start, finish = _chronoid_bounds(graph, iri)
        outcome = _literal(graph, URIRef(iri), _ph("outcome"))
        if start is None:
            status = "initialised"
        elif finish is not None:
            status = "finished"
        else:
            status = "ongoing"
        out.append({
            "iri": iri,
            "class": cls,
            "status": status,
            "outcome": outcome,
            "label": _literal(graph, URIRef(iri), _ph("label")),
        })
    return out


# -- verdict readings ----------------------------------------------------

def label_of(graph: Graph, iri: str) -> str:
    """Resolve a label through the graph by IRI (single label source)."""
    for predicate in (_ph("label"), URIRef("http://www.w3.org/2000/01/rdf-schema#label")):
        value = graph.value(URIRef(iri), predicate)
        if value is not None:
            return str(value)
    return _short(iri)


def render_readings(manifest: dict, verdict: dict, graph: Graph) -> list[str]:
    """Render ``readings`` via the manifest's declared templates.

    A ``ref`` reading resolves its label through the graph; a law with no
    result of a shape omits the reading rather than emitting a placeholder.
    """
    templates = {r["id"]: r for r in (manifest.get("readings") or [])}
    out = []
    for reading in verdict.get("readings") or []:
        decl = templates.get(reading.get("id"), {})
        template = decl.get("template", "{value}")
        label = decl.get("label", reading.get("id"))
        kind = reading.get("kind")
        if kind == "ref":
            value = label_of(graph, str(reading.get("value")))
        else:
            value = reading.get("value")
        try:
            text = template.format(label=value, value=value)
        except (KeyError, IndexError):
            text = f"{label}: {value}"
        out.append(f"{label}: {text}" if text != str(value) else f"{label}: {value}")
    return out


def render_blocks(verdict: dict, graph: Graph) -> list[str]:
    """Explain blocks from structured ``refs``/``counts`` — never by parsing.

    Names resolve to labels through the graph; counts render as numbers.
    """
    out = []
    for violation in verdict.get("violations") or []:
        witness = violation.get("witness") or {}
        refs = [label_of(graph, r) for r in witness.get("refs", [])]
        counts = [f"{c.get('name')}={c.get('value')}" for c in witness.get("counts", [])]
        detail = violation.get("detail") or violation.get("eca") or "blocked"
        bits = [detail]
        if refs:
            bits.append("involving " + ", ".join(refs))
        if counts:
            bits.append("(" + ", ".join(counts) + ")")
        out.append(" — ".join(bits))
    return out


# -- duties --------------------------------------------------------------

def pending_duties(verdict: dict, manifest: dict, graph: Graph) -> list[dict]:
    """Pending duties from the verdict, each tagged by its process instance.

    Every actionable control is built from the manifest's declared
    ``holder_role``, parameters, modality, label, and message; a ``choices``
    parameter renders as a picker whose options come from the verdict.
    """
    by_id = {e["id"]: e for e in (manifest.get("ecas") or [])}
    out = []
    for citizen, entries in (verdict.get("pending") or {}).items():
        for entry in entries:
            eca_id = entry.get("eca") if isinstance(entry, dict) else entry
            decl = by_id.get(eca_id, {})
            out.append({
                "citizen": citizen,
                "citizen_label": label_of(graph, citizen),
                "eca": eca_id,
                "eca_label": decl.get("label", eca_id),
                "message": decl.get("message", ""),
                "modality": decl.get("modality", ""),
                "holder_role": decl.get("holder_role", ""),
                "params": decl.get("params", []),
                "choices": (entry.get("choices") or {}) if isinstance(entry, dict) else {},
                "process": (entry.get("process") if isinstance(entry, dict) else None),
            })
    return out


def build_act(eca_decl: dict, citizen: str, entry_choices: dict) -> dict | None:
    """Build a complete act from declarations + verdict choice slots.

    ``selected`` binds to the acting citizen; ``choices`` takes the verdict's
    offered option. Returns None when no complete act can be built.
    """
    act: dict = {"eca": eca_decl["id"]}
    for param in eca_decl.get("params") or []:
        if param.get("source") == "selected":
            act[param["name"]] = citizen
        else:
            options = (entry_choices or {}).get(param["name"]) or []
            if not options:
                return None
            act[param["name"]] = options[0]
    return act


def phase_disagreement_warning(
    verdict: dict, windows: dict[str, list[dict]], clock_day, clock_hour
) -> str | None:
    """Surface a declared-window/oracle-phase disagreement as a warning.

    Displays the oracle's reading; never resolves the disagreement. The
    check is positional only: the phase's own declared windows do not
    contain the clock position.
    """
    phase = verdict.get("phase")
    if not phase:
        return None
    try:
        day = int(str(clock_day)) if clock_day is not None else None
    except (TypeError, ValueError):
        return None
    if day is None:
        return None
    # Find windows whose phase class name matches the oracle phase reading.
    candidates = [
        entries for cls, entries in windows.items()
        if _short(cls).lower() == str(phase).lower() or str(phase) in cls
    ]
    if not candidates:
        return None
    for entries in candidates:
        for entry in entries:
            if entry["kind"] == "point":
                point = entry["point"]
                if point.get("dayIndex") is not None and int(point["dayIndex"]) == day:
                    return None
            else:
                if entry.get("gapDays") is not None:
                    return None  # relative span: nothing to compare, no warning
                start = entry.get("start") or {}
                finish = entry.get("finish") or {}
                try:
                    start_day = int(start["dayIndex"]) if start.get("dayIndex") is not None else None
                    finish_day = int(finish["dayIndex"]) if finish.get("dayIndex") is not None else None
                except (TypeError, ValueError):
                    return None
                if start_day is not None and finish_day is not None:
                    if start_day <= day <= finish_day:
                        return None
    return (
        f"warning: oracle reports phase '{phase}' but no declared window "
        f"for it contains day {day} — displaying the oracle reading"
    )
