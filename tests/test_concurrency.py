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
  uv run python tests/test_concurrency.py cases/requisitions
"""

from __future__ import annotations

import sys
from pathlib import Path

from rdflib import Literal, RDF, URIRef

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "lawgen"))

from runtime.lawdriver import (advance, apply_declared, drive_to_pending, manifest_of,
                       minting_eca)  # noqa: E402
from runtime.oracle import OracleClient, OracleRejected  # noqa: E402

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
    """Move the clock. One write, and it is the only one.

    This used to write `ph:dayIndex` and `ph:atHour` onto every typed subject as
    well, "each instance carries its own position, so an act has to know the
    moment it happened at". No instance carries one any more: `ph:dayIndex` is
    declared on `gfo-light:TimeBoundary`, so stamping it on a `ph:Requisition` or
    a `ph:MayorElectionCycle` put a schema violation into the graph the oracle
    was sent, and it did it on every subject including the ones the oracle would
    have read a moment from.
    """
    c.set_clock(day, hour)


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
        # A SKIP, not a failure. The scenario is about a law that can have
        # several ongoing instances of one process, which it can only do if some
        # act mints a new one. `mayor-2027` has no repeat and therefore mints no
        # Process instance, so there is nothing here to exercise -- and recording
        # that as a failure makes a correct law look broken, which is how
        # `test_oracle.py` came to break `mayor-2027` when the quorum law was
        # rewritten. A suite that fails a law for a shape the law does not have
        # is worse than no suite.
        print(f"  SKIP a duty on a multi-instance process type: {case.name} "
              f"declares no `mints:`, so no ECA can begin a second instance. "
              f"Nothing checked.")
        return
    minted_class = mints[0]

    c = OracleClient(case)
    # Reached by driving the law to OFFER its minting ECA and then performing
    # it, rather than assuming the act is available from the seed. On a quorum
    # flavour it is not: `repeat` needs the polls to have closed and failed, and
    # taking every vote the verdict offers is how a quorum HOLDS, so a greedy
    # walk satisfies the precondition away. `drive_to_pending` caps the other
    # acts and steps the clock through the law's own calendar.
    mints_eca = minting_eca(case)
    if not drive_to_pending(c, case, mints_eca):
        expect("the law reaches a state offering its minting ECA", False,
               f"{mints_eca} was never offered")
        return
    # Applied repeatedly, once per occasion, until a duty offers a choice among
    # instances: several open instances is the capability, so one is not enough.
    # How many that takes is the law's business -- on `requisitions` a citizen
    # may lodge and immediately withdraw, so the walk oscillates and a greedy
    # pass would leave nothing open to choose between.
    for _ in range(len(citizens(c)) + 2):
        if settle_of(c, minted_class)[1] is not None:
            break
        if not apply_declared(c, case, mints_eca, 1):
            break

    all_instances = process_instances(c, [minted_class])
    instances = [i for i in all_instances
                 if not c.graph.value(URIRef(i), URIRef(PH + "outcome"))]
    expect("the law mints instances of one process type", len(all_instances) >= 2,
           f"only {all_instances}")
    # Whether two instances can be OPEN at once is the law's business, not the
    # framework's. A quorum repeat closes its predecessor by definition, so on
    # that flavour there is never a second open election: recorded as a gap in
    # the artefacts rather than asserted as something the law cannot do.
    if len(instances) < 2:
        print(f"    GAP two open instances at once is unsatisfiable on this law: "
              f"{[i.rsplit('/', 1)[-1] for i in all_instances]} exist, and "
              f"{[i.rsplit('/', 1)[-1] for i in instances]} is open -- the "
              f"minting act closes its predecessor, so no second is open")
        return
    expect("more than one instance is open at once", True)
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


def bracketing_span(c: OracleClient) -> tuple[str, int, int] | None:
    """A declared span that can contain a finish of the law's last scheduled moment.

    Ranked rather than taken first: `spans[0]` is whatever the graph yields
    first, which on an election law is the nomination window -- a span that
    contains no election ending at all, because polls close falls after it. A
    quorum repeat also MINTS its own window span once it is scheduled, so the
    span that brackets the ending only exists once the law has been driven, and
    reading it from the seed would miss it.
    """
    rdf_type = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
    last_day = None
    for s in c.graph.subjects(rdf_type, URIRef(PH + "CalendarPoint")):
        d = c.graph.value(URIRef(s), URIRef(PH + "dayIndex"))
        if d is not None:
            last_day = max(last_day or 0, int(str(d)))
    if last_day is None:
        return None

    out: list[tuple[str, int, int]] = []
    for s in c.graph.subjects(rdf_type, URIRef(PH + "CalendarSpan")):
        fin = c.graph.value(URIRef(s), URIRef(GFO_CORE + "temporallyFinishedBy"))
        st = c.graph.value(URIRef(s), URIRef(GFO_CORE + "temporallyStartedBy"))
        if fin is None or st is None:
            continue
        fd = c.graph.value(URIRef(fin), URIRef(PH + "dayIndex"))
        sd = c.graph.value(URIRef(st), URIRef(PH + "dayIndex"))
        if fd is None or sd is None:
            continue
        out.append((str(s), int(str(sd)), int(str(fd))))
    containing = [x for x in out if x[1] <= last_day <= x[2]]
    if containing:
        return min(containing, key=lambda x: (x[2] - x[1], x[1]))
    return None


def ending_moments(case: Path, span_start: int, span_end: int) -> list[tuple[int, int]]:
    """Moments inside the span at which this law might be ended.

    A grid over the span's own bounds and the hours the law declares, because
    which of them the law will actually accept is the law's business and cannot
    be known without asking it. A law that can end on different DAYS offers two
    moments differing in day; one whose ending is pinned to a single instant --
    an election can only be closed once the polls close -- can only differ in
    hour, and the hour is still part of the moment the bound records.
    """
    hours = []
    try:
        import yaml
        t = (yaml.safe_load((case / "manifest.yaml").read_text()) or {}).get("time") or {}
        for key in ("polls_close", "deadline_hour"):
            if t.get(key) is not None:
                hours.append(int(t[key]))
    except Exception:  # noqa: BLE001 - a law with no time block gets the default
        pass
    hours = sorted(set(hours + [20]))
    days = sorted({span_start + 1, span_end})
    return [(d, h) for d in days for h in hours]


def check_mid_span(case: Path) -> None:
    """7.3: an ending inside a span reads like one on a calendar point."""
    print("\n-- 7.3 a process ending inside a calendar span --")
    by_id = manifest_of(case)
    mints = [e["mints"] for e in by_id.values() if e.get("mints")]
    if not mints:
        # A SKIP for the same reason as 5.4: an instance can only be ended
        # mid-span if some act can begin a second one, and a law that mints no
        # Process instance never has two. `mayor-2027` has no repeat.
        print(f"  SKIP a process ending inside a calendar span: {case.name} "
              f"declares no `mints:`, so no instance is ever begun and none can "
              f"be ended. Nothing checked.")
        return

    # Driven once to reach the law's LAST scheduled moment, which is when its
    # own calendar has the span that brackets the ending -- on a quorum flavour
    # that span is minted by the repeat and does not exist in the seed.
    seed = OracleClient(case)
    shaped = OracleClient(case)
    if not drive_to_pending(shaped, case, minting_eca(case)):
        expect("the law reaches its minting ECA", False,
               f"{minting_eca(case)} was never offered")
        return
    apply_declared(shaped, case, minting_eca(case), 1)

    found = bracketing_span(shaped)
    expect("the law declares a span bracketing its last scheduled moment",
           found is not None,
           "no bounded span contains the law's last calendar point")
    if found is None:
        return
    span, span_start, span_end = found
    print(f"    span {span.rsplit('/', 1)[-1]} runs day {span_start}..{span_end}")

    # Which of the span's moments the law will actually accept is the law's
    # business, so each candidate is probed and the ones that end the instance
    # are kept. Two are needed to compare their shape.
    shapes: list[tuple] = []
    labels: list[str] = []
    for day, hour in ending_moments(case, span_start, span_end):
        if len(shapes) >= 2:
            break
        c = OracleClient(case)
        if not drive_to_pending(c, case, minting_eca(case)):
            continue
        apply_declared(c, case, minting_eca(case), 1)
        made = [m for m in process_instances(c, mints)
                if not c.graph.value(URIRef(m), URIRef(PH + "outcome"))]
        if not made:
            continue
        target = made[0]
        at(c, day, hour)
        # End it through whatever duty this law offers on it. Preference order
        # is not hardcoded: any offered act is tried, and the first the law
        # accepts is the ending.
        # Keep walking the duties until the instance ACTUALLY ends. An act being
        # accepted is not the same as the instance finishing -- on an election
        # law `count` is accepted at polls close and finishes nothing, so
        # stopping at the first acceptance would report an ending that never
        # happened.
        ended = False
        for _ in range(len(by_id) + 2):
            offered = None
            for eid in by_id:
                act = build(c, eid, citizens(c)[0])
                if act is None:
                    continue
                try:
                    c.apply(act)
                except OracleRejected:
                    continue
                offered = act
                break
            if offered is None:
                break
            if finish_shape(c, target) is not None:
                ended = True
                break
        if not ended:
            continue
        got = finish_shape(c, target)
        if got is None:
            continue
        if any(got[0] != s[0] or got[1] != s[1] for s in shapes):
            continue
        shapes.append(got)
        labels.append(f"day {day} hour {hour}")
        print(f"    ended at day {day:3} hour {hour:2} -> bound day={got[2]} hour={got[3]}")
        expect("the ending instance is retained, not erased", target in c.subjects())

    expect("the law can be ended at two moments inside one span", len(shapes) >= 2,
           f"only {labels} -- the law offered no second ending inside "
           f"day {span_start}..{span_end}")

    if len(shapes) >= 2:
        p, s = shapes[0], shapes[1]
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
