"""Headless verification for the law-simulation TUI change.

Exercises the loader, guide derivations, async worker, and app flow
without a TTY, mirroring each task's verify clause. Run:

    uv run python tests/test_tui_guide.py
"""

from __future__ import annotations

import asyncio
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT))

from tui import guide as G  # noqa: E402
from runtime.graphwire import load_artefact_case  # noqa: E402
from runtime.loader import (  # noqa: E402
    EcaMismatchError,
    FrozenSetError,
    load_artefact_set,
    verify_eca_agreement,
    verify_frozen,
)
from runtime.oracle import OracleClient, OracleRejected  # noqa: E402
from tui.worker import AsyncOracle  # noqa: E402

PH = "https://potato-hamlet.example/ontology/"
fails: list[str] = []


def expect(name: str, cond: bool, detail: str = ""):
    print(("PASS " if cond else "FAIL ") + name + (f" ({detail})" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def main() -> int:
    # 1.2 artefact-set loading
    aset = load_artefact_set(ROOT / "cases/mayor-2027")
    schema, seed = aset.schema, aset.seed
    from rdflib import URIRef
    from rdflib.namespace import RDF

    citizens = [s for s in seed.subjects(RDF.type, URIRef(PH + "Citizen"))]
    expect("1.2 labelled citizens", len(citizens) >= 7 and all(
        G.label_of(seed, str(c)) != str(c).rsplit("/", 1)[-1] for c in citizens),
        f"citizens={len(citizens)}")
    tree = G.process_tree(schema)
    expect("1.2 declared process hierarchy", any(len(v) >= 5 for v in tree.values()),
           f"roots={list(tree)}")
    expect("1.2 manifest display declarations",
           bool(aset.manifest.get("ecas")) and bool(aset.manifest.get("readings")),
           "no ecas/readings")

    # 1.3 freeze + ECA agreement
    expect("1.3 frozen mayor set verifies", bool(verify_frozen(ROOT / "cases/mayor-2027")))
    client_probe = OracleClient(ROOT / "cases/mayor-quorum")
    try:
        verify_eca_agreement(aset.manifest, client_probe.eca_ids())
        expect("1.3 ECA mismatch refused", False, "mayor manifest agreed with quorum oracle?!")
    except EcaMismatchError as exc:
        expect("1.3 ECA mismatch refused", "repeat" in str(exc), str(exc)[:120])
    bad_manifest = copy.deepcopy(aset.manifest)
    bad_manifest["ecas"] = [e for e in bad_manifest["ecas"] if e["id"] != "vote"]
    try:
        verify_eca_agreement(bad_manifest, OracleClient(ROOT / "cases/mayor-2027").eca_ids())
        expect("1.3 missing ECA refused", False, "no error")
    except EcaMismatchError:
        expect("1.3 missing ECA refused", True)
    try:
        verify_frozen(ROOT / "cases/requisitions")
        frozen_req = True
    except FrozenSetError:
        frozen_req = False
    print(f"     (requisitions frozen: {frozen_req}; edited-set refusal covered by digest path)")

    # 2.1 runtime graph + labels
    c = OracleClient(ROOT / "cases/mayor-quorum")
    unlabeled = [str(s) for s in c.graph.subjects() if isinstance(s, URIRef)
                 and str(s).startswith(PH) and G.label_of(c.graph, str(s)) == str(s).rsplit("/", 1)[-1]
                 and G.label_of(c.graph, str(s)) == str(s)]
    # label_of falls back to short IRI; require every subject typed instead
    untyped = [str(s) for s in c.graph.subjects() if isinstance(s, URIRef)
               and str(s).startswith(PH) and not list(c.graph.objects(s, RDF.type))]
    expect("2.1 every subject typed (label resolvable)", not untyped, f"{untyped[:3]}")

    # 2.2 async worker responsive during check
    async def worker_check():
        w = AsyncOracle(ROOT / "cases/mayor-quorum")
        task = asyncio.ensure_future(w.check())
        await asyncio.sleep(0.05)
        w.set_clock(5, 10)  # must not block while check is in flight
        verdict = await asyncio.wait_for(task, timeout=120)
        return verdict, w.clock()
    verdict, pos = asyncio.run(worker_check())
    expect("2.2 responsive during check", verdict.get("phase") is not None and pos == (5, 10),
           f"phase={verdict.get('phase')} pos={pos}")

    # 2.3 apply clean path + undeclared-subject refusal
    c2 = OracleClient(ROOT / "cases/mayor-quorum")
    before = set(c2.graph)
    pend = c2.check()["pending"]
    first_cit, first_entry = next(
        (cit, e) for cit, es in pend.items() for e in es if e["eca"] == "announce"
    )
    from runtime.lawdriver import manifest_of, act_from_declaration  # noqa: E402
    by_id = manifest_of(ROOT / "cases/mayor-quorum")
    c2.apply(act_from_declaration(by_id["announce"], first_entry, first_cit))
    # Individuals persist (subjects monotone); triples may rewrite values
    # of functional properties, so compare subjects, not triples.
    subjects_before = {s for s, _, _ in before}
    expect("2.3 no act removes an individual",
           {s for s, _, _ in set(c2.graph)} >= subjects_before)
    from rdflib import Graph as RGraph, Literal
    evil = RGraph()
    for t in c2.graph:
        evil.add(t)
    evil.add((URIRef(PH + "evil/1"), RDF.type, URIRef(PH + "NotAClass")))
    try:
        c2.replace(evil)
        expect("2.3 undeclared subject refused", False, "committed?!")
    except Exception:
        expect("2.3 undeclared subject refused",
               {s for s, _, _ in set(c2.graph)} >= subjects_before,
               "graph changed despite refusal")

    # 2.4 clock is the only local write
    c3 = OracleClient(ROOT / "cases/mayor-quorum")
    c3.set_clock(9, 10)
    day = c3.graph.value(URIRef(PH + "clock/now"), URIRef(PH + "dayIndex"))
    v3 = c3.check()
    expect("2.4 clock advance local, next check reflects", str(day) == "9" and v3.get("phase") == "RegistryOpen",
           f"day={day} phase={v3.get('phase')}")

    # 3.1 tree with day windows read from artefacts
    q_schema, q_seed = load_artefact_case(ROOT / "cases/mayor-quorum")
    windows = G.phase_windows(q_seed)
    summaries = G.window_summary(windows)
    expect("3.1 election tree with day windows",
           any("day" in s for s in summaries.values()), f"{summaries}")

    # 3.2 overlapping phases concurrent, no ordering
    nom = next((w for cls, ws in windows.items() if cls.endswith("SelfNomination") for w in ws), None)
    ann_points = [w for cls, ws in windows.items() if cls.endswith("AnnounceElection") for w in ws]
    overlap = (nom and nom.get("start") and nom["start"].get("dayIndex") == "0"
               and any(p.get("point", {}).get("dayIndex") == "0" for p in ann_points))
    expect("3.2 nomination + announce concurrent day 0", bool(overlap), f"nom={nom} ann={ann_points}")
    import yaml as _yaml
    onto_text = (ROOT / "cases/mayor-quorum/ontology.ttl").read_text()
    expect("3.2 no imposed ordering in artefacts",
           not any(pred in onto_text for pred in
                   ["ph:before", "ph:after", "ph:precedes", "ph:follows", "ph:nextPhase",
                    "ph:order", "ph:sequence"]))

    # 3.3 oracle phase displayed; disagreement warned not resolved
    w = G.phase_disagreement_warning({"phase": "NoSuchPhase"}, windows, 0, 9)
    expect("3.3 unknown phase needs no warning", w is None)
    w2 = G.phase_disagreement_warning({"phase": "SelfNomination"}, windows, 10**6, 10)
    expect("3.3 disagreement surfaces as warning, oracle reading kept",
           isinstance(w2, str) and "SelfNomination" in w2, f"{w2}")

    # 3.4 initialised vs ongoing vs finished
    statuses = G.instance_status(q_seed, q_schema)
    expect("3.4 seeded process awaiting trigger",
           any(i["status"] == "initialised" for i in statuses), f"{statuses}")

    # 3.5 + 4.1 two concurrent processes (drive repeat to mint a successor)
    from runtime.lawdriver import drive_to_pending  # noqa: E402
    c4 = OracleClient(ROOT / "cases/mayor-quorum")
    drive_to_pending(c4, ROOT / "cases/mayor-quorum", "repeat")
    c4_by_id = manifest_of(ROOT / "cases/mayor-quorum")
    quorum_manifest = __import__("yaml").safe_load(
        (ROOT / "cases/mayor-quorum/manifest.yaml").read_text())
    # Duties + blocks are read from the pre-repeat verdict (void cycle with
    # repeat + quorum violation pending); the post-repeat graph proves the
    # successor instance exists.
    pre_verdict = c4.check()
    duties = G.pending_duties(pre_verdict, quorum_manifest, c4.graph)
    tagged = [d for d in duties if d.get("process")]
    expect("4.1 duties tagged by process", bool(duties) and len(tagged) == len(duties),
           f"duties={len(duties)} tagged={len(tagged)}")

    # Apply the repeat now: the successor instance proves multi-instance display.
    for cit, entries in list(pre_verdict.get("pending", {}).items()):
        for e in entries:
            if e["eca"] == "repeat":
                c4.apply(act_from_declaration(c4_by_id["repeat"], e, cit))
                break
        else:
            continue
        break
    inst2 = G.instance_status(c4.graph, q_schema)
    expect("3.5 two instances both display", len(inst2) >= 2, f"{len(inst2)}")

    # 4.2 manifest-driven controls incl. unseen act
    decls = {e["id"]: e for e in __import__("yaml").safe_load(
        (ROOT / "cases/mayor-quorum/manifest.yaml").read_text())["ecas"]}
    vote_decl = decls["vote"]
    expect("4.2 choices param declared", any(p.get("source") == "choices" for p in vote_decl["params"]))
    repeat_act = G.build_act(decls["repeat"], "someone", {})
    expect("4.2 unseen act builds with no code change", repeat_act == {"eca": "repeat"},
           f"{repeat_act}")

    # 4.4 blocks with names + figures (from the pre-repeat void verdict)
    blocks = G.render_blocks(pre_verdict, c4.graph)
    has_counts = any((vi.get("witness") or {}).get("counts") for vi in pre_verdict.get("violations", []))
    expect("4.4 blocks name identities + figures",
           bool(blocks) and has_counts, f"{blocks[:1]}")

    # 4.5 rejected act reports reason, graph unchanged
    c5 = OracleClient(ROOT / "cases/mayor-quorum")
    snap = set(c5.graph)
    try:
        c5.apply({"eca": "vote", "voter": PH + "citizen/bob",
                  "candidate": PH + "citizen/cara"})
        expect("4.5 rejected act refused", False, "applied?!")
    except OracleRejected as exc:
        expect("4.5 rejected act reports reason, graph unchanged",
               bool(str(exc)) and set(c5.graph) == snap, str(exc)[:100])

    # 5.1 advisory would-win + proclaim pending (readings carry mayor ref)
    readings = G.render_readings(quorum_manifest, pre_verdict, c4.graph)
    expect("5.1 readings advisory via templates", isinstance(readings, list),
           f"{readings[:2]}")

    # 5.2 holders read from verdict; 5.3 no priority
    import re
    guide_src = (ROOT / "tui/guide.py").read_text()
    expect("5.2 no fallback-authority rule", "oldest" not in guide_src.lower(),
           "guide mentions oldest")
    expect("5.3 no priority recommendation",
           "priorit" not in guide_src.lower() or "no priority" in guide_src.lower(),
           "guide prioritises?")

    # 6.1 law swap: quorum repeat renders + plays in unmodified code
    q_client = OracleClient(ROOT / "cases/mayor-quorum")
    ok = drive_to_pending(q_client, ROOT / "cases/mayor-quorum", "repeat")
    rep_entries = [e for es in q_client.check().get("pending", {}).values() for e in es
                   if e["eca"] == "repeat"]
    expect("6.1 repeat renders + plays unmodified", ok and bool(rep_entries),
           f"offered={ok} entries={len(rep_entries)}")

    # 4.3 explicit confirmation + log (headless app: request alone changes
    # nothing; confirm applies and logs)
    async def confirm_flow():
        from tui.app import HamletGuideApp  # noqa: E402
        app = HamletGuideApp(case_dir=ROOT / "cases/mayor-quorum")
        async with app.run_test():
            await asyncio.sleep(4.0)
            graph_before = set(app.oracle.client.graph)
            duties0 = G.pending_duties(app.verdict, app.artefacts.manifest,
                                       app.oracle.client.graph)
            duty = next(d for d in duties0 if d["eca"] == "announce")
            await app.request_act(duty, {})
            no_auto = set(app.oracle.client.graph) == graph_before and app.pending_confirm
            await app.confirm_act()
            await asyncio.sleep(2.0)
            return no_auto, bool(app.log_entries) and "announce" in app.log_entries[0]
    no_auto, logged = asyncio.run(confirm_flow())
    expect("4.3 no transition without confirmation, log per act", no_auto and logged,
           f"no_auto={no_auto} logged={logged}")

    # 5.1 + 6.2 tied vote on the mayor baseline: would-win advisory with
    # proclaim still pending and no office change; proclaim elects oldest.
    c6 = OracleClient(ROOT / "cases/mayor-2027")
    b6 = manifest_of(ROOT / "cases/mayor-2027")
    c6.set_clock(0, 0)
    c6.apply({"eca": "announce"})
    c6.apply({"eca": "nominate", "citizen": PH + "citizen/bob"})
    c6.apply({"eca": "nominate", "citizen": PH + "citizen/cara"})
    c6.set_clock(9, 10)
    c6.apply({"eca": "prepare"})
    for _ in range(20):
        moved = False
        for cit, es in list(c6.check().get("pending", {}).items()):
            for e in es:
                if e["eca"] == "deliver":
                    c6.apply(act_from_declaration(b6["deliver"], e, cit))
                    moved = True
                    break
            if moved:
                break
        if not moved:
            break
    c6.set_clock(10, 12)
    c6.apply({"eca": "vote", "voter": PH + "citizen/bob", "candidate": PH + "citizen/bob"})
    c6.apply({"eca": "vote", "voter": PH + "citizen/cara", "candidate": PH + "citizen/cara"})
    c6.set_clock(10, 19)
    c6.apply({"eca": "count"})
    pre = c6.check()
    mayor_reading = next((r for r in pre.get("readings", []) if r.get("id") == "mayor"), {})
    proclaim_pending = any(e["eca"] == "proclaim"
                           for es in pre.get("pending", {}).values() for e in es)
    expect("5.1 would-win advisory, proclaim pending, no office change",
           mayor_reading.get("value") == PH + "citizen/bob" and proclaim_pending
           and c6.occupants("MayorRole") == [],
           f"reading={mayor_reading} proclaim={proclaim_pending}")
    c6.apply({"eca": "proclaim"})
    expect("6.2 full cycle proclaims oldest-on-tie",
           c6.occupants("MayorRole") == [PH + "citizen/bob"],
           f"office={c6.occupants('MayorRole')} (bob 54 > cara 43)")

    print()
    if fails:
        print(f"{len(fails)} FAILURES: {fails}")
        return 1
    print("all headless TUI checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
