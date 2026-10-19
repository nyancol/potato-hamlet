"""Review gate: freeze a reviewed artefact set, verify frozen sets.

Freeze (human act after reviewing drafts + green checks):
  uv run python tools/lawgen/freeze.py cases/mayor-2027
  -> runs tools/lawgen/check.py first; on pass writes manifest freeze hash
     (sha256 over law.txt + ontology.ttl + rules.lean + manifest body),
     plus the version of the shared physical vocabulary it was reviewed with.

Verify (consumer/TUI entry point, Phase 2 calls this before loading):
  uv run python tools/lawgen/freeze.py --verify cases/mayor-2027
  -> exit 0 iff frozen and no file changed; names changed files otherwise,
     and names the shared vocabulary separately when that is what moved.

The shared vocabulary has a review of its own, independent of any case:
  uv run python tools/lawgen/freeze.py --vocabulary
  uv run python tools/lawgen/freeze.py --verify-vocabulary
  -> checks the file parses, is grounded and carries no individuals, then
     writes or verifies its own hash in framework/physical.freeze.
     It needs a review of its own because it is the meaning UNDERNEATH every
     case: a case can verify against a vocabulary nobody has looked at, which
     is the one thing a per-case hash cannot tell you.

The shared populated world has a review of its own on the same pattern:
  uv run python tools/lawgen/freeze.py --world
  uv run python tools/lawgen/freeze.py --verify-world
  -> checks the file parses, every individual is typed by a declared class,
     every predicate is declared, there is exactly one clock, and citizens
     carry label and age, then writes or verifies its own hash in
     framework/world.freeze. The clock's reading is excluded from the hash.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent

sys.path.insert(0, str(ROOT))
from runtime.graphwire import world_version  # noqa: E402
# population.ttl is tracked: the spec puts the seeded individuals in the
# variant layout, and a freeze that ignores the seed is not a freeze of the
# set. It was omitted while the seed still lived inside ontology.ttl, which
# WAS tracked -- moving the individuals out silently dropped them from the
# hash.
TRACKED = ["law.txt", "ontology.ttl", "population.ttl", "rules.lean"]

# The shared physical vocabulary is a framework artefact rather than part of
# any case, so it is tracked too. Without it a case could verify against a
# vocabulary it was not reviewed with -- the set would look frozen while the
# meaning underneath it had moved, which is the failure `TRACKED` itself was
# widened once already when population.ttl was dropped from it.
SHARED = "framework/physical.ttl"

# Recorded in the manifest body as the vocabulary's own content hash, so
# verification can say WHICH vocabulary a reviewed law was reviewed against
# rather than only that something changed. An upgrade of the vocabulary then
# prompts an informed re-review instead of an automatic one.
SHARED_VERSION_KEY = "shared_vocabulary"

# Recorded in the manifest body as the world's content hash (clock reading
# excluded, mirroring world_version), so verification can say WHICH world a
# reviewed law was reviewed against. A world change then prompts an informed
# re-review instead of a silent reinterpretation.
WORLD_VERSION_KEY = "world"


def shared_version() -> str:
    """The shared vocabulary's content hash, or `absent`.

    Absent rather than an error, because the vocabulary is AVAILABLE to a law
    and required of none: a set that draws on none of it freezes and verifies
    exactly as it did before the file existed.
    """
    path = ROOT / SHARED
    if not path.exists():
        return "absent"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def digest(case: Path, manifest_body: dict) -> str:
    h = hashlib.sha256()
    for name in TRACKED:
        h.update((case / name).read_bytes())
        h.update(b"\0")
    h.update(yaml.safe_dump(manifest_body, sort_keys=True).encode())
    h.update(b"\0")
    return "sha256:" + h.hexdigest()


def manifest_body(case: Path) -> dict:
    data = yaml.safe_load((case / "manifest.yaml").read_text())
    body = {k: v for k, v in data.items() if k != "freeze"}
    # The vocabulary version is part of the body, so moving the shared file
    # changes every case's hash and the manifest says which version each was
    # reviewed against. Written on freeze rather than read at verify time, so
    # the recorded version is the one review happened on.
    body[SHARED_VERSION_KEY] = shared_version()
    body[WORLD_VERSION_KEY] = world_version()
    return body


def freeze(case: Path) -> int:
    proc = subprocess.run(
        ["uv", "run", "python", "tools/lawgen/check.py", str(case.relative_to(ROOT))],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    print(proc.stdout, end="")
    if proc.returncode != 0:
        print("freeze refused: machine checks fail.", file=sys.stderr)
        return 1
    body = manifest_body(case)
    data = yaml.safe_load((case / "manifest.yaml").read_text())
    data.pop(SHARED_VERSION_KEY, None)
    data.pop(WORLD_VERSION_KEY, None)
    data["freeze"] = digest(case, body)
    data[SHARED_VERSION_KEY] = body[SHARED_VERSION_KEY]
    data[WORLD_VERSION_KEY] = body[WORLD_VERSION_KEY]
    (case / "manifest.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    print(f"frozen {case.relative_to(ROOT)}: {data['freeze']}")
    print(f"  shared vocabulary: {data[SHARED_VERSION_KEY]}")
    print(f"  world: {data[WORLD_VERSION_KEY]}")
    return 0


def verify(case: Path) -> int:
    data = yaml.safe_load((case / "manifest.yaml").read_text())
    frozen = data.get("freeze")
    if not frozen:
        print(f"unfrozen: {case.relative_to(ROOT)} has no freeze mark (run tools/lawgen/freeze.py).")
        return 1
    changed = []
    for name in TRACKED:
        if not (case / name).exists():
            changed.append(f"{name} (missing)")
    body = {k: v for k, v in data.items() if k != "freeze"}
    # The shared vocabulary is named separately and by name, because it is the
    # one tracked file outside the case and the one whose movement is a review
    # decision rather than an edit: saying WHICH version a set was reviewed
    # against is the difference between an informed re-review and a blind one.
    current = shared_version()
    recorded = data.get(SHARED_VERSION_KEY)
    if recorded != current:
        changed.append(
            f"shared vocabulary {SHARED} (reviewed against {recorded or 'no recorded version'}, "
            f"now {current})"
        )
    current_world = world_version()
    recorded_world = data.get(WORLD_VERSION_KEY)
    if recorded_world != current_world:
        changed.append(
            f"world {WORLD} (reviewed against {recorded_world or 'no recorded version'}, "
            f"now {current_world})"
        )
    if digest(case, body) != frozen:
        # Which file changed cannot be recovered from a single combined hash,
        # so the whole set is reported. Built from TRACKED rather than written
        # out: a hardcoded list goes stale the moment a file is added, and then
        # it names files that did not change while omitting the one that did.
        # Per-file mtimes guide the author to the culprit.
        changed.append(
            "one or more of " + " / ".join(TRACKED) + " / manifest body "
            "(hash mismatch; the combined hash cannot say which)"
        )
    if changed:
        print(f"refused: {case.relative_to(ROOT)} changed after freeze:")
        for c in changed:
            print(f"  {c}")
        return 1
    print(f"verified frozen: {case.relative_to(ROOT)}")
    return 0


VOCABULARY_MARK = "framework/physical.freeze"

WORLD = "framework/world.ttl"
WORLD_MARK = "framework/world.freeze"


def check_world(path: Path | None = None) -> list[str]:
    """The shared populated world must be reviewable on its own.

    Checked by reusing the gate's own functions rather than a second
    implementation: individuals typed by a class nothing declares, or
    carrying a predicate nothing declares, would otherwise surface only
    inside whichever law first merged the world in. Types and predicates
    resolve against the shared vocabulary plus the framework-invariant
    classes and properties, which live per-case but are fixed by the
    framework rather than declared by any law.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check import (FRAMEWORK_CLASSES,  # noqa: PLC0415
                       FRAMEWORK_PROPERTIES, IMPORTED, declared_classes,
                       declared_properties, expand, parse)
    from rdflib import RDF, URIRef  # noqa: PLC0415

    target = path or ROOT / WORLD
    wg, errs = parse(target)
    if wg is None:
        return errs or [f"{target}: could not parse"]
    errors = list(errs)

    sg, serrs = parse(ROOT / SHARED)
    if sg is None:
        return errors + serrs or [f"{SHARED}: could not parse"]
    allowed_classes = declared_classes(sg) | {
        expand(f"ph:{n}") for n in FRAMEWORK_CLASSES
    }
    allowed_props = declared_properties(sg) | {
        expand(f"ph:{n}") for n in list(FRAMEWORK_PROPERTIES) + ["label"]
    }

    for subj in sorted({s for s in wg.subjects() if isinstance(s, URIRef)}, key=str):
        types = [t for t in wg.objects(subj, RDF.type) if isinstance(t, URIRef)]
        if not types:
            errors.append(
                f"{target.name}: <{subj}> has no rdf:type, so a consumer "
                f"cannot tell what it is"
            )
            continue
        for t in types:
            if t in allowed_classes or str(t).startswith(IMPORTED):
                continue
            errors.append(
                f"{target.name}: <{subj}> is typed <{t}>, which neither the "
                f"shared vocabulary nor the framework invariants declare as "
                f"a class"
            )
    for subj, pred, _ in wg:
        if pred == RDF.type or not isinstance(pred, URIRef):
            continue
        if pred in allowed_props or str(pred).startswith(IMPORTED):
            continue
        errors.append(
            f"{target.name}: <{subj}> carries {str(pred).rsplit('/', 1)[-1]}, "
            f"which neither the shared vocabulary nor the framework "
            f"invariants declare, so no law could read it"
        )

    # One simulation, one shared reality, one clock.
    clocks = [s for s in wg.subjects(RDF.type, expand("ph:Clock"))]
    if len(clocks) != 1:
        errors.append(
            f"{target.name}: carries {len(clocks)} ph:Clock individuals, but "
            f"the world holds exactly one present shared by every law"
        )
    citizen = expand("ph:Citizen")
    for subj in sorted(wg.subjects(RDF.type, citizen), key=str):
        if list(wg.objects(subj, expand("ph:label"))) == []:
            errors.append(f"{target.name}: citizen <{subj}> lacks ph:label")
        if list(wg.objects(subj, expand("ph:age"))) == []:
            errors.append(f"{target.name}: citizen <{subj}> lacks ph:age")
    return errors


def freeze_world() -> int:
    errors = check_world()
    if errors:
        print(f"freeze refused: {WORLD} does not satisfy the world rules.")
        for e in errors:
            print(f"  {e}")
        return 1
    version = world_version()
    mark = {"freeze": version,
            "note": "Reviewed as a framework artefact. Changing this file "
                    "invalidates every case freeze recorded against it. The "
                    "clock's reading is not part of the hash."}
    (ROOT / WORLD_MARK).write_text(yaml.safe_dump(mark, sort_keys=False))
    print(f"frozen {WORLD}: {version}")
    return 0


def verify_world() -> int:
    mark_path = ROOT / WORLD_MARK
    if not mark_path.exists():
        print(f"unfrozen: {WORLD} has no review mark "
              f"(run tools/lawgen/freeze.py --world).")
        return 1
    errors = check_world()
    for e in errors:
        print(f"  {e}")
    frozen = (yaml.safe_load(mark_path.read_text()) or {}).get("freeze")
    current = world_version()
    if errors or frozen != current:
        print(f"refused: {WORLD} changed after review:")
        if frozen != current:
            print(f"  reviewed {frozen}, now {current}")
        return 1
    print(f"verified frozen: {WORLD}")
    return 0


def check_vocabulary() -> list[str]:
    """The shared vocabulary must satisfy the same schema rules a law's does.

    Checked by reusing the gate's own functions rather than a second
    implementation: a vocabulary that parses and grounds differently under
    `check.py` than under `freeze.py` would mean the two disagreed about what
    a legal declaration is, which is the thing the freeze exists to prevent.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check import check_grounding, check_tbox, parse  # noqa: PLC0415

    graph, errs = parse(ROOT / SHARED)
    if graph is None:
        return errs or [f"{SHARED}: could not parse"]
    return errs + check_grounding(graph) + check_tbox(graph)


def freeze_vocabulary() -> int:
    errors = check_vocabulary()
    if errors:
        print(f"freeze refused: {SHARED} does not satisfy the schema rules.")
        for e in errors:
            print(f"  {e}")
        return 1
    version = shared_version()
    mark = {"freeze": version,
            "note": "Reviewed as a framework artefact. Changing this file "
                    "invalidates every case freeze recorded against it."}
    (ROOT / VOCABULARY_MARK).write_text(yaml.safe_dump(mark, sort_keys=False))
    print(f"frozen {SHARED}: {version}")
    return 0


def verify_vocabulary() -> int:
    mark_path = ROOT / VOCABULARY_MARK
    if not mark_path.exists():
        print(f"unfrozen: {SHARED} has no review mark "
              f"(run tools/lawgen/freeze.py --vocabulary).")
        return 1
    errors = check_vocabulary()
    for e in errors:
        print(f"  {e}")
    frozen = (yaml.safe_load(mark_path.read_text()) or {}).get("freeze")
    current = shared_version()
    if errors or frozen != current:
        print(f"refused: {SHARED} changed after review:")
        if frozen != current:
            print(f"  reviewed {frozen}, now {current}")
        return 1
    print(f"verified frozen: {SHARED}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    if argv[1] == "--verify":
        return verify((ROOT / argv[2]).resolve())
    if argv[1] == "--vocabulary":
        return freeze_vocabulary()
    if argv[1] == "--verify-vocabulary":
        return verify_vocabulary()
    if argv[1] == "--world":
        return freeze_world()
    if argv[1] == "--verify-world":
        return verify_world()
    return freeze((ROOT / argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
