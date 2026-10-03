# Tasks

## 1. Lean transition functions in both rules files

- [x] 1.1 Add `Act` inductive with `FromJson` plus per-ECA `apply*` functions and `apply` dispatch to `artefacts/mayor-2027/rules.lean` (reusing the existing `?` guards, `Except String` rejections) and verify `lake env lean` is clean
- [x] 1.2 Port the `Act`/`apply` sections to `artefacts/mayor-quorum/rules.lean` with the quorum `repeatAfterVoid` case generalizing `repeatFresh`, and verify `lake env lean` is clean
- [x] 1.3 Add transition property checks (vote appends exactly one entry, prepare yields all-distributed, double announce errors) exercisable via `#eval`/probe and verify each holds on sample snapshots

## 2. Oracle `apply` verb and rebuild

- [x] 2.1 Implement `cmdApply` in `potato-hamlet-lean/OracleMain.lean` parsing the `{"act","snapshot"}` envelope and returning the new snapshot or a JSON rejection, and verify `lake build oracle` succeeds
- [x] 2.2 Rebuild both case oracles via `scripts/build_oracle.py` and verify `list`/`check` outputs are unchanged while `apply` serves the new verb on each binary

## 3. Apply-trace tests

- [x] 3.1 Extend `scripts/test_oracle.py` with a full 2027 apply trace (announce through proclaim) plus rejection cases (double vote, out-of-window nominate) and verify all pass
- [x] 3.2 Extend `scripts/test_quorum.py` with a below-half turnout apply trace ending in the quorum violation and a repeat-act producing the day-40 fresh snapshot, and verify all pass
- [x] 3.3 Add pending/apply conformance checks (every pending act applies clean; representative non-pending acts reject) and verify no ECA disagrees between `pendingOf` and `apply`

## 4. Docs, freeze, and acceptance

- [x] 4.1 Document the transition table and `apply` envelope protocol in `artefacts/README.md` and verify the documented example payloads parse as JSON
- [x] 4.2 Re-run `scripts/check.py` and re-freeze both artefact sets, and verify `--verify` passes on each
- [x] 4.3 Run `openspec validate eca-apply-transitions --type change --strict` and verify planning artifacts are complete and consistent
