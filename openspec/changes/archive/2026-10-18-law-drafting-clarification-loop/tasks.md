# Tasks

The loop's guarantee is that a draft presented as complete can be frozen. The product loop runs in pi; everything here serves the contracts it calls plus the headless driver that proves them without a credential: get the questions asked, get them answered, and let the existing gate refuse whatever is left.

## 0. Pin the contract before building anything

- [x] 0.1 DECIDED: the report is a SEPARATE structured return value, not a fenced block inside the draft. The draft files are the artefact under review and go into the freeze hash verbatim, so a block inside `ontology.ttl` would either have to be stripped before freezing -- and anything left in by mistake becomes part of the frozen TBox -- or be a permanent part of a file the gate already reads as schema. A separate value keeps the contract explicit and the draft exactly what it will be. Shape: the three draft files, plus a list of {step, why-ungroundable}. Now project-owned as a schema file plus validator, which the pi report tool binds via `outputSchema`.
- [x] 0.2 DONE, and it falsified design decision 5. Three shapes of undeclared reference, three outcomes: (A) an individual typed by an undeclared class -- caught by `check_population`, though the walk ran first and died with a traceback; (B) a declared class whose SUPERCLASS nobody declares -- **all checks passed, missed entirely**; (C) an undeclared property in the seed -- caught by seed parity. A fourth found while fixing it: (D) a property whose `rdfs:domain` or `rdfs:range` names an undeclared class -- also missed. `check_tbox` asks whether a class REACHES GFO, and a dangling `ph:` superclass does not disturb that, because the class keeps its own grounding and the invented name rides alongside it. B and D are exactly the shape a drafting process produces when it invents a class name and wires it in.
- [x] 0.3 DONE, and the answer is the OPPOSITE of what the task assumed: a new check IS needed. Corrected in `design.md` decision 5 and in the `law-extraction` delta. One check, in `check_tbox`, covering superclass, domain and range together -- every `ph:` class a declaration NAMES must itself be declared in the merged graph. Mutation-verified on all three shapes (B, D-domain, D-range) and no regression on any shipped case. Worth having independently of this change: it catches a broken subclass axiom in any draft. A second defect fixed alongside: `check.py` TRACEBACKED instead of reporting on a malformed set, and `freeze.py` runs the gate first, so the caller saw an opaque crash rather than the finding.

## 1. The prompt contract

- [x] 1.1 Add to `onto-v2.md`, `lean-v1.md` and `manifest-v2.md` an instruction to report every step the text requires that no declared object, capability or action accounts for, in the strict schema 0.1 settled (validator rejects anything else)
- [x] 1.2 Add the **positive** half to each: where a declared capability accounts for the step, proceed and declare against it, and do not ask. The threshold stated only negatively produces performative reporting
- [x] 1.3 Add to each an explicit instruction not to invent a mechanism in order to avoid reporting a step, and say why: an invented class is checkable and a concealed guess is not
- [x] 1.4 Verify the four framework invariants still read as mandated after these additions — the failure `shared-physical-vocabulary` task 6.3 exists to prevent, and this change edits the same files 6.3 verifies
- [x] 1.5 Define how law-derived seeds (calendar, instances, states, roles) are drafted in-loop against the world fixture: by reference to world IRIs, never restating a world-owned individual — verify a drafted seed set passes the gate over the world merge

## 2. The report contract and the fake (no Python loop driver)

- [x] 2.1 Ship the project-owned report schema file plus a validator CLI: strict accept/reject on the `{step, why-ungroundable}` shape, non-zero exit on violation — verify the validator accepts a well-formed report and rejects free text and a fenced-block-in-draft
- [x] 2.2 Record the pi tool contract the schema binds (tool name, `outputSchema` = the schema file, `structuredContent` returned to callers; free-text output is not a handoff) — built via pi, defined here; verify by reading the contract back against design decisions 6–8
- [x] 2.3 Ship a deterministic fake that reads a scripted sequence of reports, so convergence and the question round are testable without a credential
- [x] 2.4 Make the fake able to report questions — a fake that never asks would make the loop look converged forever, which is the one behaviour most worth testing. Verify by running the headless driver against it and confirming it stops with questions outstanding
- [x] 2.5 Keep `redraft.py` render-and-stop unconditionally and add machine-readable render output pi can call — verify current render behaviour is byte-identical for existing users

## 3. The headless test driver (CI-only, never user-facing)

- [x] 3.1 Build the minimal driver: render, validate the report, run the gate over the world fixture — extract, collect the report, and while it is non-empty present the steps as questions and re-extract with the answers. Verify it runs with no credential
- [x] 3.2 Terminate only on an empty report, and refuse to present a draft as complete while any remain: a headless run ending non-empty writes drafts plus report and exits non-zero — verify the exit code
- [x] 3.3 Feed an answer back into the next pass in a form the fake can use, and verify an answer actually changes the draft rather than being logged
- [x] 3.4 Guard against a non-terminating driver: a step that is asked about and comes back ungrounded must not be asked forever. Record what the driver does when it makes no progress, rather than leaving it to spin
- [x] 3.5 Record the pi-side loop rules this driver mirrors (question UI, no-progress continuation guard, `pi -p` writes-and-exits rule) — built via pi, specified here; verify each has a stated owner (pi) and a headless equivalent in 3.1–3.4

## 4. Prove the convergence claim

- [x] 4.1 Drive the headless driver against `mayor-2027` with the fake over the world fixture and confirm the resulting draft passes the gate
- [x] 4.2 Stop the driver early — present a draft with an undeclared class still in it — and confirm the gate refuses it. This is the whole basis of design decision 5 and it is the change's central claim
- [x] 4.3 Verify a law whose text is fully covered by the shared vocabulary asks **nothing**, which is the failure mode where the prompt's negative instruction has produced performative reporting
- [x] 4.4 Verify the same question is never asked twice across two passes of one driver run

## 5. Unblock the neighbour

- [x] 5.1 `shared-physical-vocabulary` task 6.3 now has a draft to run the gate on. Either complete it here against the headless driver plus fake, or hand it back with the draft to hand — but do not leave it blocked on a step this change has just built
- [x] 5.2 Record that 6.3's verification is of the **prompt's** content against a draft, so a fake-fed driver is the faithful thing to verify it with, rather than implying a model was exercised

## 6. Record what the loop exposes about the vocabulary

- [x] 6.1 The loop's questions are a report on `framework/physical.ttl`. Note which questions recur across the two election laws, since a question asked twice is evidence the shared stage lacks a concept every law can reach for
- [x] 6.2 Do NOT grow the vocabulary in this change. A concept needing its own capability is the signal worth having, and answering it here would convert a question into an assumption without anyone deciding to
- [x] 6.3 State the recurring questions in this change's design as the input `shared-physical-vocabulary` decision 6 asked for — *"worth revisiting if the same local class appears across laws"* — now answered by evidence rather than by a guess

## 7. Declare the world prerequisite

- [x] 7.1 Consumes `shared-populated-world` (world store, world-pinned freeze, gate merge): no world code is built here, and the driver in section 3 runs against that change's world fixture — verify the dependency is stated in design and this task, and that nothing in sections 1–6 authors world individuals
