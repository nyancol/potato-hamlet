"""Driving a law without knowing which law it is.

The suites need to reach an interesting state before they can assert anything
about it. How you get there differs per law: a mayor election has to be
announced, prepared and polled; a requisition has to be lodged. Hardcoding
either sequence in a test is per-law code in the one place the framework
forbids it -- and it makes the suite fail on the third law rather than telling
you anything.

So: take whatever the verdict offers, build each act from the manifest's
declarations with values from the verdict's own choice slots, and apply it.
That is exactly what a consumer does, which makes reaching a state a test of
the contract rather than a fact about one law.

Shared with tools/lawgen/check.py, which uses the same walk for the graph round trip
and the reading declarations.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from rdflib import URIRef

PH = "https://potato-hamlet.example/ontology/"
RDF_TYPE = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")


def manifest_of(case: Path) -> dict[str, dict]:
    """The case's ECAs, keyed by id."""
    data = yaml.safe_load((case / "manifest.yaml").read_text())
    return {e["id"]: e for e in data.get("ecas", [])}


def act_from_declaration(eca: dict, entry: dict, citizen: str) -> dict | None:
    """Build a complete act from the manifest's declarations, or None.

    A parameter sourced from `selected` binds to the citizen the verdict
    offered the duty to; one sourced from `choices` takes an option from the
    entry's own choice slots. If either runs dry there is no complete act to
    offer, and the entry is skipped rather than half-sent.
    """
    act: dict = {"eca": eca["id"]}
    choices = entry.get("choices") or {}
    for prm in eca.get("params") or []:
        if prm.get("source") == "selected":
            act[prm["name"]] = citizen
        else:
            options = choices.get(prm["name"]) or []
            if not options:
                return None
            act[prm["name"]] = options[0]
    return act


def pending_acts(client, by_id: dict) -> list[dict]:
    """Every complete act the verdict is currently offering."""
    out = []
    for citizen, entries in (client.check().get("pending") or {}).items():
        for entry in entries:
            eca_id = entry.get("eca") if isinstance(entry, dict) else entry
            eca = by_id.get(eca_id)
            if eca is None:
                continue
            act = act_from_declaration(eca, entry, citizen)
            if act is not None:
                out.append(act)
    return out


def play_forward(client, by_id: dict, limit: int = 40) -> tuple[list[dict], list[str]]:
    """Take whatever the verdict offers until nothing applies.

    Returns the acts applied and any subject-monotonicity failure seen on the
    way -- erasure being prohibited either way.
    """
    from runtime.oracle import OracleRejected

    applied: list[dict] = []
    losses: list[str] = []
    seen = client.subjects()
    for _ in range(limit):
        moved = False
        for act in pending_acts(client, by_id):
            try:
                client.apply(act)
                applied.append(act)
                moved = True
            except OracleRejected:
                continue
            break
        if not moved:
            break
        now = client.subjects()
        for gone in sorted(seen - now):
            losses.append(f"after {applied[-1]['eca']}: <{gone}>")
        if losses:
            break
        seen |= now
    return applied, losses


def advance(client, case: Path, rounds: int = 3) -> list[dict]:
    """Drive a law forward a few steps, ignoring what is not applicable.

    For a suite that needs "some state with duties in it" rather than a
    particular one. Returns every act applied.
    """
    by_id = manifest_of(case)
    applied: list[dict] = []
    for _ in range(rounds):
        step, _ = play_forward(client, by_id, limit=12)
        applied.extend(step)
        if not step:
            break
    return applied


def apply_declared(client, case: Path, eca_id: str, times: int) -> list[dict]:
    """Apply one DECLARED ECA `times`, built from the manifest.

    Which ECA creates an instance is not hardcoded: it is the one carrying
    `mints`. And a greedy walk is not always what a test wants -- a law where an
    instance can be created and withdrawn alternately will oscillate forever
    under `advance`, leaving nothing open to choose between.
    """
    from runtime.oracle import OracleRejected

    by_id = manifest_of(case)
    eca = by_id.get(eca_id)
    if eca is None:
        return []
    applied: list[dict] = []
    for _ in range(times):
        moved = False
        for act in pending_acts(client, by_id):
            if act["eca"] != eca_id:
                continue
            try:
                client.apply(act)
                applied.append(act)
                moved = True
            except OracleRejected:
                continue
            break
        if not moved:
            break
    return applied


def minting_eca(case: Path) -> str | None:
    """The ECA that declares it creates a Process instance, if there is one."""
    for eid, e in manifest_of(case).items():
        if e.get("mints"):
            return eid
    return None


def calendar_moments(client) -> list[tuple[int, int]]:
    """Every moment the law's frozen calendar declares, in order.

    Read from the graph rather than computed, because the framework's own claim
    is that a consumer orders a law's calendar points against the clock to find
    where it is -- so stepping the clock through them is how any law is walked,
    whatever its days are called.
    """
    from rdflib import URIRef

    rdf_type = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
    out: list[tuple[int, int]] = []
    for s in client.graph.subjects(rdf_type, URIRef(PH + "CalendarPoint")):
        d = client.graph.value(URIRef(s), URIRef(PH + "dayIndex"))
        if d is None:
            continue
        h = client.graph.value(URIRef(s), URIRef(PH + "atHour"))
        out.append((int(str(d)), int(str(h)) if h is not None else 10))
    return sorted(set(out))


def drive_to_pending(client, case: Path, eca_id: str, per_eca: int = 1,
                     limit: int = 60) -> bool:
    """Reach a state where `eca_id` is OFFERED, without performing it.

    Some laws declare a minting act that is available from the seed; others
    need a precondition first. A quorum repeat needs the polls to have closed
    and failed, and a greedy walk can never get there: taking every vote the
    verdict offers is exactly how a quorum HOLDS. So this applies each other
    declared ECA at most `per_eca` times, which leaves a law short of its own
    quorum, and steps the clock through the law's declared calendar so a duty
    that is not due yet becomes due.

    How many times each other act may be applied is a policy of this helper, not
    a fact about any law -- which is why it is a parameter.
    """
    from runtime.oracle import OracleRejected

    by_id = manifest_of(case)
    used: dict[str, int] = {}

    def try_apply() -> bool:
        for act in pending_acts(client, by_id):
            name = act["eca"]
            if name == eca_id or used.get(name, 0) >= per_eca:
                continue
            try:
                client.apply(act)
            except OracleRejected:
                continue
            used[name] = used.get(name, 0) + 1
            return True
        return False

    # The current position first: a law whose minting act is available from the
    # seed must be seen before the clock is moved, or stepping past the window
    # would lose the only moment the duty was offered.
    moments = calendar_moments(client)
    for day, hour in [(None, None)] + [(d, h) for d, h in moments] + [(10**6, 10)]:
        if day is not None:
            client.set_clock(day, hour)
        for _ in range(limit):
            if any(a["eca"] == eca_id for a in pending_acts(client, by_id)):
                return True
            if not try_apply():
                break
    return any(a["eca"] == eca_id for a in pending_acts(client, by_id))


def all_pending(client) -> list[dict]:
    """Every pending entry, flattened, whatever its shape."""
    return [e for es in (client.check().get("pending") or {}).values() for e in es]
