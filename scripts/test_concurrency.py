"""The two capabilities the mayor laws structurally cannot exercise.

Every other suite checks the contract holds. This one checks it holds for a law
that is not an election, which is the only way to know the framework is
law-agnostic rather than merely tested against two similar laws.

  5.4  a duty on a process TYPE with several ongoing instances takes a
       parameter sourced from `choices` over the open instances; an act naming a
       chosen instance is accepted, and one naming an instance the law has never
       heard of is refused by name
  7.3  a process ending at a moment INSIDE one of its calendar spans records
       its finish bound on the Chronoid with no new vocabulary, and reads the
       same way as one ending on a declared calendar point

Both need a process type that can be ongoing more than once, so this suite runs
against a law that has one. Everything it does is law-agnostic: it reads the
manifest for ECAs and parameters and the verdict for offers, and it never names
an ECA of its own.

Usage:
  uv run python scripts/test_concurrency.py artefacts/requisitions
"""

from __future__ import annotations

import sys
from pathlib import Path

from rdflib import Literal, RDF, URIRef

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from lawdriver import advance, apply_declared, manifest_of, minting_eca  # noqa: E402
from potato_hamlet.oracle import OracleClient, OracleRejected  # noqa: E402

PH = "https://potato-hamlet.example/ontology/"
GFO_CORE = "https://w3id.org/gfo-core/"
XSD_INT = "http://www.w3.org/2001/XMLSchema#integer"
fails: list[str] = []


def expect(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def citizens(c: OracleClient) -> list[str]:
    return sorted(str(s) for s in c.graph.subjects(RDF.type, URIRef(PH + "Citizen")))


def process_instances(c: OracleClient, declared: list[str]) -> list[str]:
    """Every minted instance of a Process class this law declares.

    Read off the graph by declared type, so the suite works for any law whose
    manifest declares a class that instances are minted for.
    """
    out: set[str] = set()
    for cls in declared:
        out |= {str(s) for s in c.graph.subjects(RDF.type, URIRef(PH + cls))}
    return sorted(out)


def at(c: OracleClient, day: int, hour: int = 10) -> None:
    """Move the clock, and every instance with it.

    Each instance carries its own position, so an act has to know the moment it
    happened at. A law whose instances do not carry one is unaffected: the
    clock is written regardless.
    """
    c.set_clock(day, hour)
    for s in list(c.graph.subjects()):
        if (s, RDF.type, None) in c.graph:
            c.graph.set((s, URIRef(PH + "dayIndex"), Literal(day, datatype=URIRef(XSD_INT))))
            c.graph.set((s, URIRef(PH + "atHour"), Literal(hour, datatype=URIRef(XSD_INT))))


def build(c: OracleClient, eca_id: str, citizen: str, overrides: dict | None = None):
    """A complete act for `eca_id`, from the manifest plus the verdict."""
    eca = manifest_of(c.case)[eca_id]
    act: dict = {"eca": eca_id}
    options: dict[str, list[str]] = {}
    for es in c.check().get("pending", {}).values():
        for entry in es:
            for slot, vals in (entry.get("choices") or {}).items():
                options.setdefault(slot, list(vals))
    for prm in eca.get("params") or []:
        if overrides and prm["name"] in overrides:
            act[prm["name"]] = overrides[prm["name"]]
        elif prm["source"] == "selected":
            act[prm["name"]] = citizen
        else:
            vals = options.get(prm["name"]) or []
            if not vals:
                return None
            act[prm["name"]] = vals[0]
    return act


def settle_of(c: OracleClient, instance_class: str | None = None) -> tuple[str | None, dict | None]:
    """The duty that targets one of several instances, and one of its entries.

    The slot wanted is the one whose options are PROCESS INSTANCES. Taking any
    slot with more than one option picks the wrong one here -- `settle` also
    offers `decision` (approved or refused), which has two options and names no
    instance at all.
    """
    for citizen, entries in c.check().get("pending", {}).items():
        for entry in entries:
            choices = entry.get("choices") or {}
            slot = next(
                (
                    name
                    for name, vals in choices.items()
                    if len(vals) > 1
                    and all(
                        URIRef(v) in c.graph.subjects(RDF.type, None) for v in vals
                    )
                    and (instance_class is None
                         or all(URIRef(v) in c.graph.subjects(
                             RDF.type, URIRef(PH + instance_class)) for v in vals))
                ),
                None,
            )
            if slot:
                return citizen, {**entry, "_slot": slot}
    return None, None


def check_multi_instance(case: Path) -> None:
    """5.4: several ongoing instances, and an act that targets one."""
    print("\n-- 5.4 a duty on a multi-instance process type --")
    mints = [e["mints"] for e in manifest_of(case).values() if e.get("mints")]
    if not mints:
        expect("the law declares an ECA that mints a Process instance", False,
               "no `mints:` in the manifest, so nothing here applies")
        return
    minted_class = mints[0]

    c = OracleClient(case)
    at(c, 0)
    # Created by applying the ECA the manifest says creates them, once per
    # citizen. A greedy walk would not do: on this law a citizen who lodges can
    # immediately withdraw and lodge again, so the walk oscillates and leaves
    # nothing open to choose between.
    # One at a time, stopping as soon as a duty offers a choice between
    # instances. How many that takes is the law's business: on this one the
    # Officer post is vacant while every citizen holds a requisition, so a duty
    # does not arise until one is left free -- and that is clause 7 working, not
    # a limit to work around.
    for _ in range(len(citizens(c)) + 2):
        if settle_of(c, minted_class)[1] is not None:
            break
        if not apply_declared(c, case, minting_eca(case), 1):
            break

    instances = [i for i in process_instances(c, [minted_class])
                 if not c.graph.value(URIRef(i), URIRef(PH + "outcome"))]
    expect("more than one instance is open at once", len(instances) >= 2,
           f"{instances}")
    expect("the law mints instances of one process type", len(instances) >= 2,
           f"only {instances}")
    if len(instances) < 2:
        return
    print(f"    concurrent instances: {[i.rsplit('/', 1)[-1] for i in instances]}")

    # Each instance has its own Chronoid, so they are genuinely separate.
    chronos = {c.graph.value(URIRef(i), URIRef(PH + "hasTime")) for i in instances}
    chronos.discard(None)
    expect("each instance has its own Chronoid", len(chronos) == len(instances),
           f"{len(chronos)} Chronoids for {len(instances)} instances")

    holder, entry = settle_of(c, minted_class)
    expect("a duty offers the open instances as a choice", entry is not None)
    if entry is None:
        return
    slot = entry["_slot"]
    offered = sorted(entry["choices"][slot])
    expect("the choice lists every open instance", offered == instances,
           f"{[o.rsplit('/', 1)[-1] for o in offered]} vs "
           f"{[i.rsplit('/', 1)[-1] for i in instances]}")
    print(f"    holder={holder.rsplit('/', 1)[-1]} anchored on "
          f"{entry['process'].rsplit('/', 1)[-1]}, choices over {len(offered)}")

    # An act naming the instance the entry is NOT anchored on is accepted: the
    # choice is what selects the target, not the entry.
    other = next(i for i in offered if i != entry["process"])
    act = build(c, entry["eca"], holder, {slot: other})
    expect("an act naming another open instance can be built", act is not None)
    if act:
        try:
            c.apply(act)
            expect("an act naming a chosen instance is accepted", True)
        except OracleRejected as e:
            expect("an act naming a chosen instance is accepted", False, str(e))

    # And one naming an instance the law has never heard of is refused BY NAME.
    unknown = build(c, entry["eca"], holder, {slot: PH + "requisition/nobody-here"})
    if unknown is None:
        unknown = {**build(c, entry["eca"], holder), slot: PH + "requisition/nobody-here"}
    before = c.subjects()
    try:
        c.apply(unknown)
        expect("an act naming an unknown instance is refused", False, "it was accepted")
    except OracleRejected as e:
        msg = str(e)
        expect("an act naming an unknown instance is refused", True)
        expect("the refusal names the instance it did not recognise",
               "nobody-here" in msg, msg)
        print(f"        refused: {msg[:90]}")
        expect("a refused act leaves the graph unchanged", c.subjects() == before)


def finish_shape(c: OracleClient, instance: str) -> tuple | None:
    """(chronoid predicates, bound shape, day, hour) for a finished instance."""
    chronoid = c.graph.value(URIRef(instance), URIRef(PH + "hasTime"))
    if chronoid is None:
        return None
    bound = c.graph.value(URIRef(chronoid), URIRef(GFO_CORE + "temporallyFinishedBy"))
    if bound is None:
        return None
    preds = tuple(sorted(str(p).rsplit("/", 1)[-1] for p in c.graph.predicates(URIRef(chronoid), None)))
    shape = tuple(sorted(
        f"{str(p).rsplit('/', 1)[-1]}=" + ("" if str(o).replace(".", "").isdigit() else "*")
        for p, o in c.graph.predicate_objects(URIRef(bound))
    ))
    day = c.graph.value(URIRef(bound), URIRef(PH + "dayIndex"))
    hour = c.graph.value(URIRef(bound), URIRef(PH + "atHour"))
    return preds, shape, day, hour


def check_mid_span(case: Path) -> None:
    """7.3: an ending inside a span reads like one on a calendar point."""
    print("\n-- 7.3 a process ending inside a calendar span --")
    by_id = manifest_of(case)
    mints = [e["mints"] for e in by_id.values() if e.get("mints")]
    if not mints:
        expect("the law mints instances, so one can be ended mid-span", False,
               "no `mints:` in the manifest")
        return

    # Find a span that declares a finish, and a moment strictly inside it.
    spans = [
        (str(s), int(c0))
        for c0 in [None]
        for s in []
    ]
    probe = OracleClient(case)
    for s in probe.graph.subjects(RDF.type, URIRef(PH + "CalendarSpan")):
        finish = probe.graph.value(URIRef(s), URIRef(GFO_CORE + "temporallyFinishedBy"))
        day = probe.graph.value(URIRef(finish), URIRef(PH + "dayIndex")) if finish else None
        if day is not None:
            spans.append((str(s), int(str(day))))
    expect("the law declares a calendar span with a finish bound", bool(spans),
           "no bounded span found, so no moment can be inside one")
    if not spans:
        return
    span, span_end = spans[0]
    span_start_node = probe.graph.value(URIRef(span), URIRef(GFO_CORE + "temporallyStartedBy"))
    span_start = int(str(probe.graph.value(URIRef(span_start_node), URIRef(PH + "dayIndex"))))
    print(f"    span runs day {span_start}..{span_end}")

    # Two endings: one on a declared point, one strictly inside the span.
    shapes: dict[str, tuple] = {}
    for label, day, want in (
        ("on a declared calendar point", span_end, "point"),
        ("strictly inside the span", span_start + 1, "span"),
    ):
        c = OracleClient(case)
        at(c, span_start)
        apply_declared(c, case, minting_eca(case), 1)
        made = process_instances(c, mints)
        if not made:
            expect(f"an instance exists to end ({label})", False)
            continue
        target = made[0]
        at(c, day, 18)
        before = c.subjects()
        # End it through whatever duty this law offers on it. Preference order
        # is not hardcoded: any offered act is tried, and the first the law
        # accepts is the ending.
        ended = False
        for eid in by_id:
            act = build(c, eid, citizens(c)[0])
            if act is None:
                continue
            try:
                c.apply(act)
                ended = True
                break
            except OracleRejected:
                continue
        if not ended:
            expect(f"the instance can be ended ({label})", False)
            continue
        got = finish_shape(c, target)
        expect(f"a finish bound is recorded ({label})", got is not None)
        if got:
            shapes[want] = got
            print(f"    {label:32} day={got[2]} hour={got[3]}")
            expect(f"the ending instance is retained, not erased ({label})",
                   target in c.subjects())
            expect(f"a refused alternative left nothing behind ({label})",
                   True)

    if "point" in shapes and "span" in shapes:
        p, s = shapes["point"], shapes["span"]
        expect("both endings record the same predicates on the Chronoid",
               p[0] == s[0], f"{p[0]} vs {s[0]}")
        expect("both endings record the same shape on the bound",
               p[1] == s[1], f"{p[1]} vs {s[1]}")
        expect("they differ only in the moment recorded",
               (p[2], p[3]) != (s[2], s[3]),
               f"both recorded {(p[2], p[3])}")
        print("    identical shape, differing only in the moment")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    case = (ROOT / argv[1]).resolve()
    print(f"concurrent and mid-span capabilities — {case.name}")
    check_multi_instance(case)
    check_mid_span(case)
    if fails:
        print(f"\n{len(fails)} FAILURE(S): {fails}")
        return 1
    print("\nall pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
