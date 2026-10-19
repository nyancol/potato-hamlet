/**
 * Credential-free self-test for the pi drafting package.
 *
 * Runs with plain node (type stripping; no build step):
 *   NODE_PATH=<pi-install>/.mise/node_modules node pi/selftest/run.ts
 * or via pi/selftest/run.sh, which locates typebox for you.
 *
 * Covers: strict report validation incl. cross-check against
 * tools/lawgen/validate_report.py over shared fixtures; report-tool execute;
 * gate wrapper verdicts live (check refused/passed, build, freeze) plus the
 * exec-failure distinction; loop decisions (ask once, stall, reextract,
 * headless exits); settle-guard decisions; skill guidance-only wording.
 * Needs no model and no key. Exits non-zero on any failure.
 */
import { execFileSync } from "node:child_process";
import { cpSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { decide, freshSteps, headlessOutcome, validateReport, buildPassPrompt, parseGateOutput } from "../extensions/drafting/loop-lib.ts";
import { executeReport, sha256hex } from "../extensions/drafting/report-core.ts";
import { parseExitCodeVerdict, runHamletBuild, runHamletCheck, runHamletFreeze } from "../extensions/drafting/gate-core.ts";
import { consumePassId, endLoop, isRedelivery, loopState, noteSent, recordPass, resetLoop } from "../extensions/drafting/loop-state.ts";
import { settleProblems } from "../extensions/drafting/settle-guard.ts";

const ROOT = new URL("../..", import.meta.url).pathname.replace(/\/$/, "");
let failures = 0;

function expect(name: string, cond: boolean, detail = ""): void {
	console.log(`${cond ? "PASS" : "FAIL"} ${name}${cond || !detail ? "" : ` (${detail})`}`);
	if (!cond) failures += 1;
}

function repoValidator(text: string): { ok: boolean; out: string } {
	try {
		const out = execFileSync("uv", ["run", "python", "tools/lawgen/validate_report.py", "--stdin"], {
			cwd: ROOT,
			input: text,
			encoding: "utf8",
			timeout: 60_000,
		});
		return { ok: true, out: out as string };
	} catch {
		return { ok: false, out: "" };
	}
}

function main(): void {
	// --- strict validation, both mirrors, shared fixtures -----------------
	const good = JSON.stringify({ report: [{ step: "Who delivers?", "why-ungroundable": "No capability accounts for delivery" }] });
	const empty = JSON.stringify({ report: [] });
	const fixtures: Array<[string, boolean]> = [
		[empty, true],
		[good, true],
		['"just some free text"', false],
		[JSON.stringify({ report: [{ step: "", "why-ungroundable": "x" }] }), false],
		[JSON.stringify({ report: [{ step: "s" }] }), false],
		[JSON.stringify({ report: [{ step: "s", "why-ungroundable": "w", extra: 1 }] }), false],
		[JSON.stringify({ unexpected: [] }), false],
	];
	for (const [text, wantOk] of fixtures) {
		let data: unknown;
		try {
			data = JSON.parse(text);
		} catch {
			data = text;
		}
		const mine = validateReport(typeof data === "string" ? data : data).length === 0;
		const theirs = repoValidator(text).ok;
		expect(`validator agrees (want ${wantOk ? "accept" : "reject"}): ${text.slice(0, 60)}`, mine === wantOk && theirs === wantOk && mine === theirs);
	}

	// --- report-tool execute ----------------------------------------------
	const outcome = executeReport({
		ontologyTtl: "@prefix ph: <x> .",
		rulesLean: "def foo := 1",
		manifestYaml: "case: probe",
		report: { report: [{ step: "Who delivers?", "why-ungroundable": "No capability" }] },
		passId: "pass-1",
	});
	expect("execute content is blocks (never a bare string)", Array.isArray(outcome.content) && outcome.content.length === 1 && outcome.content[0]!.type === "text" && typeof outcome.content[0]!.text === "string");
	expect("execute returns structuredContent the strict check accepts", validateReport(outcome.structuredContent).length === 0);
	expect("execute details carry drafts + convergence flag", outcome.details.drafts["ontology.ttl"] === "@prefix ph: <x> ." && outcome.details.converged === false);
	expect("execute details carry passId", outcome.details.passId === "pass-1");
	expect("content text echoes passId", outcome.content[0]!.text.includes("passId: pass-1"));
	// sha256 verification
	for (const [name, text] of Object.entries(outcome.details.drafts)) {
		const expected = sha256hex(text);
		expect(`sha256 match for ${name}`, outcome.details.draftHashes[name] === expected,
			`got ${outcome.details.draftHashes[name]} want ${expected}`);
	}
	expect("content text quotes draft hashes", outcome.content[0]!.text.includes("sha256="));
	const converged = executeReport({ ontologyTtl: "t", rulesLean: "l", manifestYaml: "m", report: { report: [] } });
	expect("empty report marks converged", converged.details.converged === true);
	expect("converged content is still blocks", Array.isArray(converged.content) && converged.content.length === 1);
	let threw = false;
	try {
		executeReport({ ontologyTtl: "", rulesLean: "l", manifestYaml: "m", report: { report: [] } });
	} catch {
		threw = true;
	}
	expect("missing draft file throws (failed tool result, model retries)", threw);
	threw = false;
	try {
		executeReport({ ontologyTtl: "t", rulesLean: "l", manifestYaml: "m", report: { report: [{ step: "", "why-ungroundable": "w" }] } });
	} catch {
		threw = true;
	}
	expect("strict violation throws", threw);
	// prose-only: no structured report exists at all
	expect("prose-only never parses as a report", validateReport("polite uncertainty in prose").length > 0);

	// --- loop decisions ----------------------------------------------------
	const asked = new Set<string>();
	const r1 = { report: [{ step: "S1", "why-ungroundable": "W1" }] };
	const a1 = decide(r1, [], asked);
	expect("non-empty fresh report asks", a1.kind === "ask" && a1.steps.length === 1);
	const asked2 = new Set(["S1"]);
	expect("freshSteps never returns an asked step", freshSteps(r1, asked2).length === 0);
	expect("asked-and-still-ungrounded stalls", decide(r1, [], asked2).kind === "stalled");
	expect("empty validated report converges", decide({ report: [] }, [], new Set()).kind === "converged");
	expect("missing structured report re-extracts", decide(null, null, new Set()).kind === "reextract");
	expect("invalid structured report re-extracts with reasons", decide(r1, ["report[0].step must not be empty"], new Set()).kind === "reextract");
	expect("headless converged exits 0", headlessOutcome(false, { kind: "converged" }).exitCode === 0);
	expect("headless ask exits 1 with write", (() => { const o = headlessOutcome(false, { kind: "ask", steps: [] }); return o.exitCode === 1 && o.write; })());
	expect("headless stalled exits 1", headlessOutcome(true, { kind: "stalled" }).exitCode === 1);
	const prompt = buildPassPrompt({ rendered: { "ontology.ttl": "PROMPT" }, answers: { S1: "A1" }, skillRef: "/repo/pi/skills/drafting/SKILL.md", maxPasses: 5 });
	expect("pass prompt carries render, answers, skill ref, tool instruction",
		prompt.includes("PROMPT") && prompt.includes("Q: S1") && prompt.includes("A: A1") &&
		prompt.includes("SKILL.md") && prompt.includes("report_ungroundable_steps exactly once"));
	expect("check.py marker parses as pass", parseGateOutput(0, "--- x: ok ---\n\nall checks pass: set may proceed.", "").kind === "pass");

	// --- settle guard decisions --------------------------------------------
	const loopOpts = { repoRoot: "/tmp", caseDir: "c", outDir: "/tmp/loop-out", bank: {}, maxPasses: 5, gateFull: false };
	expect("inactive loop settles freely", settleProblems().length === 0);
	resetLoop(loopOpts);
	expect("in-flight first pass settles freely (nothing completed yet)", settleProblems().length === 0);
	noteSent();
	recordPass(null, null);
	expect("completed pass with no report blocks settle", settleProblems().length > 0);
	recordPass({ report: [] }, []);
	expect("converged record settles freely", settleProblems().length === 0);
	loopState.asked = ["S"];
	recordPass({ report: [{ step: "S", "why-ungroundable": "W" }] }, []);
	expect("non-empty record blocks settle naming the step", settleProblems().some((p) => p.includes('"S"')));
	noteSent(); // driver already sent the follow-up: guard stands down
	expect("sent follow-up stands the guard down mid-flight", settleProblems().length === 0);
	recordPass({ report: [{ step: "S", "why-ungroundable": "W" }] }, ["report[0].step must not be empty"]);
	expect("invalid record blocks settle", settleProblems().length > 0);
	loopState.asked = ["S", "S"];
	recordPass({ report: [] }, []);
	expect("re-asked step blocks settle", settleProblems().some((p) => p.includes("twice")));
	endLoop();
	expect("ended loop settles freely", settleProblems().length === 0 && loopState.active === false);

	// --- schema mirrors carry the same strictness ---------------------------
	const tsSchemas = readFileSync(join(ROOT, "pi/extensions/drafting/report-schemas.ts"), "utf8");
	const jsonSchema = JSON.parse(readFileSync(join(ROOT, "framework/clarification-report.schema.json"), "utf8")) as {
		required: string[];
		additionalProperties: boolean;
		properties: { report: { items: { required: string[]; properties: Record<string, { minLength?: number }> } } };
	};
	expect("TypeBox mirror requires exactly step + why-ungroundable",
		/\bstep\b/.test(tsSchemas) && tsSchemas.includes('"why-ungroundable"') &&
		JSON.stringify(jsonSchema.properties.report.items.required.sort()) === JSON.stringify(["step", "why-ungroundable"]));
	expect("TypeBox mirror forbids extras like the JSON schema",
		(tsSchemas.match(/additionalProperties: false/g) ?? []).length >= 2 && jsonSchema.additionalProperties === false);
	expect("TypeBox mirror requires non-empty strings like the JSON schema",
		(tsSchemas.match(/minLength: 1/g) ?? []).length >= 2 &&
		jsonSchema.properties.report.items.properties.step.minLength === 1 &&
		jsonSchema.properties.report.items.properties["why-ungroundable"].minLength === 1);

	// --- passId tracking and redelivery ------------------------------------
	resetLoop(loopOpts);
	expect("no passId consumed yet", loopState.lastPassId === null && loopState.consumedPassIds.size === 0);
	consumePassId("pass-1");
	expect("consumePassId records last", loopState.lastPassId === "pass-1");
	expect("isRedelivery detects consumed", isRedelivery("pass-1") === true);
	expect("isRedelivery is false for new", isRedelivery("pass-2") === false);
	expect("null/undefined never redelivered", isRedelivery(null) === false && isRedelivery(undefined) === false);
	recordPass({ report: [] }, [], "pass-2");
	expect("recordPass records passId", loopState.lastPassId === "pass-2" && isRedelivery("pass-2") === true);
	endLoop();

	// --- gate wrappers live -------------------------------------------------
	const checkVerdict = runHamletCheck("cases/mayor-2027", { repoRoot: ROOT });
	expect("check wrapper passes mayor-2027", checkVerdict.kind === "pass", JSON.stringify(checkVerdict).slice(0, 200));
	const scratch = mkdtempSync(join(tmpdir(), "hamlet-gate-")) + "/case";
	cpSync(join(ROOT, "cases/mayor-2027"), scratch, { recursive: true });
	writeFileSync(join(scratch, "ontology.ttl"), readFileSync(join(scratch, "ontology.ttl"), "utf8") + "\nph:BallotVote rdfs:subClassOf ph:SomethingNobodyDeclared .\n");
	const refused = runHamletCheck(scratch, { repoRoot: ROOT });
	expect("check wrapper refusal names the finding",
		refused.kind === "refused" && (refused.findings.join(" ").includes("SomethingNobodyDeclared")),
		JSON.stringify(refused).slice(0, 200));
	const execFailed = runHamletCheck("cases/mayor-2027", { repoRoot: "/nonexistent-root-xyz" });
	expect("broken environment is execFailed, never a refusal", execFailed.kind === "execFailed");
	const buildVerdict = runHamletBuild("cases/mayor-2027", { repoRoot: ROOT });
	expect("build wrapper reports mayor-2027 verbatim (pass or named refusal, never silent)",
		buildVerdict.kind !== "execFailed", JSON.stringify(buildVerdict).slice(0, 200));
	const freezeVerdict = runHamletFreeze("cases/mayor-2027", { repoRoot: ROOT });
	expect("freeze wrapper relays the frozen verdict",
		freezeVerdict.kind === "pass" || (freezeVerdict.kind === "refused" && freezeVerdict.findings.length > 0),
		JSON.stringify(freezeVerdict).slice(0, 200));
	expect("exit-code verdict: silent crash is execFailed", parseExitCodeVerdict(2, "", "").kind === "execFailed");

	// --- skill is guidance only ---------------------------------------------
	const skill = readFileSync(join(ROOT, "pi/skills/drafting/SKILL.md"), "utf8");
	const banned = ["ask the user", "re-extract", "another pass", "next pass", "keep going", "until converged", "repeat until", "iterate until"];
	const hits = banned.filter((p) => skill.toLowerCase().includes(p));
	expect("skill holds no loop-driving instructions", hits.length === 0, hits.join(", "));
	expect("skill states it never drives", /never drive/i.test(skill));

	console.log(failures === 0 ? "\nall pass" : `\n${failures} FAILURE(S)`);
	process.exit(failures === 0 ? 0 : 1);
}

main();
