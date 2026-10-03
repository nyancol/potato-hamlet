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

Shared with scripts/check.py, which uses the same walk for the graph round trip
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
    from potato_hamlet.oracle import OracleRejected

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


def all_pending(client) -> list[dict]:
    """Every pending entry, flattened, whatever its shape."""
    return [e for es in (client.check().get("pending") or {}).values() for e in es]
