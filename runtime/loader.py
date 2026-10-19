"""Loading of frozen artefact sets for the Spirit of the Hamlet guide.

Reads ``ontology.ttl`` as schema, ``population.ttl`` as seed, and
``manifest.yaml`` as display declarations. Refuses sets whose freeze mark
does not verify or whose manifest ECA ids do not match the oracle's
``list`` — naming the offending files or ids rather than loading partially.

The freeze digest mirrors ``tools/lawgen/freeze.py``: sha256 over
law.txt + ontology.ttl + population.ttl + rules.lean plus the manifest
body (which records the shared-vocabulary and world versions review
happened on).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from rdflib import Graph

from .graphwire import load_artefact_case, world_version

TRACKED = ["law.txt", "ontology.ttl", "population.ttl", "rules.lean"]
SHARED = "framework/physical.ttl"
SHARED_VERSION_KEY = "shared_vocabulary"
WORLD_VERSION_KEY = "world"


class FrozenSetError(Exception):
    """The set is unfrozen or changed after its freeze mark."""


class EcaMismatchError(Exception):
    """The manifest declares ECAs the oracle does not list (or vice versa)."""


def shared_version(root: Path) -> str:
    path = root / SHARED
    if not path.exists():
        return "absent"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _project_root(case: Path) -> Path:
    # case is <root>/cases/<name>; framework lives at <root>/framework.
    for parent in [case, *case.parents]:
        if (parent / "framework").is_dir() or (parent / "openspec").is_dir():
            return parent
    return case.parent.parent


def digest(case: Path, manifest_body: dict) -> str:
    h = hashlib.sha256()
    for name in TRACKED:
        h.update((case / name).read_bytes())
        h.update(b"\0")
    h.update(yaml.safe_dump(manifest_body, sort_keys=True).encode())
    h.update(b"\0")
    return "sha256:" + h.hexdigest()


def verify_frozen(case_dir: str | Path) -> dict:
    """Verify the freeze mark; return the manifest on success.

    Raises FrozenSetError naming the offending files on any mismatch.
    """
    case = Path(case_dir)
    data = yaml.safe_load((case / "manifest.yaml").read_text())
    frozen = (data or {}).get("freeze")
    if not frozen:
        raise FrozenSetError(
            f"{case} has no freeze mark (run tools/lawgen/freeze.py); refusing to load"
        )
    root = _project_root(case.resolve())
    changed: list[str] = []
    for name in TRACKED:
        if not (case / name).exists():
            changed.append(f"{name} (missing)")
    current_shared = shared_version(root)
    recorded_shared = data.get(SHARED_VERSION_KEY)
    if recorded_shared != current_shared:
        changed.append(
            f"shared vocabulary {SHARED} (reviewed against "
            f"{recorded_shared or 'no recorded version'}, now {current_shared})"
        )
    current_world = world_version()
    recorded_world = data.get(WORLD_VERSION_KEY)
    if recorded_world != current_world:
        changed.append(
            f"world framework/world.ttl (reviewed against "
            f"{recorded_world or 'no recorded version'}, now {current_world})"
        )
    body = {k: v for k, v in data.items() if k != "freeze"}
    try:
        if digest(case, body) != frozen:
            changed.append(
                "one or more of " + " / ".join(TRACKED) + " / manifest body "
                "(hash mismatch; the combined hash cannot say which)"
            )
    except OSError as exc:
        changed.append(f"unreadable tracked file: {exc}")
    if changed:
        raise FrozenSetError(
            f"refused: {case} changed after freeze: " + "; ".join(changed)
        )
    return data


def verify_eca_agreement(manifest: dict, oracle_ids: list[str]) -> None:
    """The manifest's ECA ids SHALL match the oracle's ``list``.

    Raises EcaMismatchError naming the offending ids.
    """
    declared = [e["id"] for e in manifest.get("ecas", [])]
    missing = [i for i in declared if i not in oracle_ids]
    extra = [i for i in oracle_ids if i not in declared]
    if missing or extra:
        parts = []
        if missing:
            parts.append("manifest declares but oracle does not list: " + ", ".join(missing))
        if extra:
            parts.append("oracle lists but manifest does not declare: " + ", ".join(extra))
        raise EcaMismatchError("; ".join(parts))


@dataclass
class ArtefactSet:
    """A verified, loaded artefact set."""

    case: Path
    manifest: dict
    schema: Graph
    seed: Graph
    ecas_by_id: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.manifest.get("case", self.case.name)


def load_artefact_set(
    case_dir: str | Path, oracle_eca_ids: list[str] | None = None
) -> ArtefactSet:
    """Verify the freeze mark, load schema + seed + manifest, check ECAs.

    ``oracle_eca_ids`` is the oracle's ``list`` output; when supplied, a
    mismatch against the manifest refuses the load. The graph merge
    (shared vocabulary + world) is owned by ``graphwire.load_artefact_case``,
    which additionally refuses a world drift.
    """
    case = Path(case_dir)
    manifest = verify_frozen(case)
    if oracle_eca_ids is not None:
        verify_eca_agreement(manifest, oracle_eca_ids)
    schema, seed = load_artefact_case(case)
    return ArtefactSet(
        case=case,
        manifest=manifest,
        schema=schema,
        seed=seed,
        ecas_by_id={e["id"]: e for e in manifest.get("ecas", [])},
    )
