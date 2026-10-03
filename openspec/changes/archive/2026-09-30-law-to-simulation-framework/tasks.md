# Tasks

## 1. Framework contract and artefact scaffolding

- [x] 1.1 Create `artefacts/mayor-2027/{law.txt,ontology.ttl,rules.lean,manifest.yaml}` skeleton with the mayor election text as `law.txt` and verify the directory layout matches the spec
- [x] 1.2 Write the versioned Step 1 prompt template pinned to the framework contract (GFO-light mapping, ECA shape, Nat-day arithmetic, mirror-by-name) and verify a redraft of an unchanged `law.txt` produces a structurally empty diff
- [x] 1.3 Document the snapshot/verdict JSON schemas and oracle CLI protocol (`list`, `check`) in `artefacts/README.md` and verify each documented example payload parses as JSON

## 2. Step 1 extraction harness with checks and review gate

- [x] 2.1 Implement the draft-generation script (law.txt in, draft ttl+lean+manifest out) and verify it runs end-to-end on the mayor text producing all three draft files
- [x] 2.2 Wire machine checks (`lake build` for Lean incl. Prop/Bool agreement theorems, OWL parse plus GFO-light consistency) with diagnostics feedback and verify a deliberately broken draft fails with the offending file named
- [x] 2.3 Implement the human review gate (freeze mark; consumers refuse edited-after-freeze sets naming changed files) and verify the loader check rejects an edited-after-freeze set

## 3. Lean oracle for the mayor law

- [x] 3.1 Implement snapshot JSON I/O (`FromJson`/`ToJson`) with IRI-string entity ids and Nat days, and verify round-trip of a sample snapshot via `#eval` or a JSON test
- [x] 3.2 Implement ECA conditions as Bool/Prop twins with agreement theorems (announce, nominate window, all-distributed, polls-open, winner with oldest-on-tie, fallback oldest-authority) and verify `lake build` is green
- [x] 3.3 Implement the compiled oracle exe (`list`, `check` with per-citizen pending plus violations-with-witnesses) and verify the 39-of-40-ballots snapshot returns false plus the missing citizen/candidate witness

## 4. Quorum-repeat flavor probe and acceptance

- [x] 4.1 Freeze `artefacts/mayor-quorum/` (baseline text plus quorum-validity with 30-day repeat, prep dates recomputed relative to the new election date, registry and ballots reset) through the Step 1 gate and verify its artefacts pass all machine checks
- [x] 4.2 Verify the quorum oracle reports invalid plus the `{voted, total}` witness on a below-half turnout snapshot, and a 30-day-later election date with fresh announce/prepare dates on the repeat
- [x] 4.3 Run `openspec validate law-to-simulation-framework --type change --strict` and verify planning artifacts are complete and consistent
