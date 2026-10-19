# Pi-side clarification-loop contract

This file DEFINES what pi builds; it is not itself the pi extension. The
session command, the report tool, the headless `check`/`build`/`freeze`
wrappers, the question UI, and the drafting skill are built via pi. What this
repo owns is the strict handoff they bind to: the schema, the validator, and
the rules below. (Design decisions 6–8.)

## 1. The report tool (binds the schema)

- **Tool name:** `report_ungroundable_steps`
- **`outputSchema`:** `framework/clarification-report.schema.json` — the
  project-owned strict shape for `{step, why-ungroundable}` entries.
- **What it returns:** the three draft files (ontology Turtle, Lean, manifest
  YAML) plus `structuredContent` carrying the report object. Callers read the
  report from `structuredContent`, never from free text.
- **Free-text output is not a handoff.** A pass that phrases uncertainty
  politely in prose must not parse as converged; only the schema-conforming
  structured value counts. The validator (`tools/lawgen/validate_report.py`)
  rejects free text and fenced blocks with a non-zero exit.
- **Empty report means converged.** Generation is complete only when the
  report is empty, and nothing presents a draft as complete while any entries
  remain (spec: Assisted generation with pinned prompt).

Verified against design decisions 6–8: decision 6 (the extractor contract is a
schema the pi side binds its report tool to via `outputSchema`), decision 7
(pi drives the product loop; no loop code lands in this repo), decision 8
(convergence is checkable on both sides by the same validator — "empty report"
means the same thing in CI and in-session).

## 2. The loop rules the headless driver mirrors (owner: pi)

Built via pi, specified here. Each rule names its pi owner and the headless
equivalent in `tools/lawgen/clarification_driver.py` (tasks 3.1–3.4):

- **Question UI (owner: pi session).** The session puts each reported step to
  the author as a question rather than proceeding on a guess. Headless
  equivalent: the driver prints each fresh step as `Q (pass N)` and records
  it in `questions.json` (3.1), stopping non-zero when an answer is missing.
- **No-progress continuation guard (owner: pi extension).** An unconditional
  continue would re-ask a step that comes back ungrounded without end; the
  continuation condition stops asking what is already asked. Headless
  equivalent: a step in `asked` that returns ungrounded is never re-asked —
  the driver records "no progress" and exits non-zero (3.4).
- **`pi -p` writes-and-exits rule (owner: pi extension).** A headless pi run
  has nobody to ask (`ctx.ui` is absent), so it writes drafts plus the strict
  report and exits non-zero, never inventing answers. Headless equivalent:
  any run ending with the report non-empty writes drafts plus `report.json`
  and exits non-zero (3.2).

## 3. Why a fake is the faithful verifier
`shared-physical-vocabulary` task 6.3 is verified against the headless driver
plus fake, and that is the faithful thing to verify it with rather than
implying a model was exercised: 6.3's verification is of the *prompt's*
content against a draft — that the new instruction did not displace the four
framework invariants — not of a model's behaviour. A deterministic fake
feeding scripted reports isolates exactly that: the prompt text pins the
invariants, the converged draft carries them, and the gate checks them. A
model in the middle would test the model, not the prompt.

## 4. Tool call shapes (implemented in `pi/`)

- **`report_ungroundable_steps`** — params: `ontologyTtl`, `rulesLean`,
  `manifestYaml` (each non-empty text), optional `populationTtl`, plus
  `report` in the strict schema shape. Returns the drafts in `details`
  (branch state the command reads back), the entry count and converged flag,
  and the report as `structuredContent`. Throws on a missing draft or a
  strict violation, so pi reports a failed tool result and the model retries.
  A well-formed pass always succeeds here; convergence is the command's
  decision, never the tool's.
- **`hamlet_check`** — params: `caseDir`, optional `full` (default
  schema-only). Runs `tools/lawgen/check.py` over the world fixture. A refusal
  returns the named findings with `isError: true`; a broken environment
  throws instead — never confused.
- **`hamlet_build`** — params: `caseDir`. Runs `tools/lawgen/build_oracle.py`;
  same refusal/error split.
- **`hamlet_freeze`** — params: `caseDir`. Runs
  `tools/lawgen/freeze.py --verify`; same split.

Each shape above runs as written: `bash pi/selftest/run.sh` exercises every
execute path (scripted calls, live gate runs, refusal-vs-crash split) with
no model and no key.
