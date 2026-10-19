/**
 * Pure clarification-loop decision logic.
 *
 * Zero imports — not even typebox — so it runs under plain `node` with no
 * install step. The pi glue (tools, command, settle guard) is thin over
 * these functions, and the self-test exercises them directly. The strict
 * report check mirrors `tools/lawgen/validate_report.py`; the cross-check in
 * `pi/selftest/run.ts` runs both over shared fixtures so the mirror cannot
 * drift silently.
 */

export interface ReportEntry {
	step: string;
	"why-ungroundable": string;
}

export interface ClarificationReport {
	report: ReportEntry[];
}

const ALLOWED_TOP_KEYS = ["report"];
const ALLOWED_ENTRY_KEYS = ["step", "why-ungroundable"];

/** Strict violations; empty means well-formed. Mirrors validate_report.py. */
export function validateReport(data: unknown): string[] {
	if (typeof data !== "object" || data === null || Array.isArray(data)) {
		return [`report must be a JSON object, got ${Array.isArray(data) ? "array" : typeof data}`];
	}
	const obj = data as Record<string, unknown>;
	const errors: string[] = [];
	for (const key of Object.keys(obj)) {
		if (!ALLOWED_TOP_KEYS.includes(key)) {
			errors.push(`unexpected top-level keys: ${JSON.stringify([key])} (only 'report' is allowed)`);
		}
	}
	if (!("report" in obj)) return [...errors, "missing required key 'report'"];
	const items = obj["report"];
	if (!Array.isArray(items)) return [...errors, `'report' must be a list, got ${typeof items}`];
	items.forEach((entry: unknown, i: number) => {
		const where = `report[${i}]`;
		if (typeof entry !== "object" || entry === null || Array.isArray(entry)) {
			errors.push(`${where} must be an object, got ${Array.isArray(entry) ? "array" : typeof entry}`);
			return;
		}
		const rec = entry as Record<string, unknown>;
		for (const key of Object.keys(rec)) {
			if (!ALLOWED_ENTRY_KEYS.includes(key)) {
				errors.push(`${where} has unexpected keys: ${JSON.stringify([key])}`);
			}
		}
		for (const key of ALLOWED_ENTRY_KEYS) {
			if (!(key in rec)) {
				errors.push(`${where} is missing required key ${JSON.stringify(key)}`);
			} else if (typeof rec[key] !== "string") {
				errors.push(`${where}.${key} must be a string, got ${typeof rec[key]}`);
			} else if ((rec[key] as string).trim() === "") {
				errors.push(`${where}.${key} must not be empty`);
			}
		}
	});
	return errors;
}

/** Entries not asked before, in order. An asked step never comes back. */
export function freshSteps(report: ClarificationReport, asked: Set<string>): ReportEntry[] {
	return report.report.filter((e) => !asked.has(e.step));
}

export type LoopAction =
	| { kind: "converged" }
	| { kind: "ask"; steps: ReportEntry[] }
	| { kind: "stalled" }
	| { kind: "reextract"; reasons: string[] };

/**
 * One decision for one pass. `validity` holds validateReport() output for
 * the pass's structured report, or null when the pass delivered no
 * structured report at all (prose-only: never convergence).
 */
export function decide(
	report: ClarificationReport | null,
	validity: string[] | null,
	asked: Set<string>,
): LoopAction {
	if (report === null || validity === null) {
		return { kind: "reextract", reasons: ["no structured report delivered; free text is not a handoff"] };
	}
	if (validity.length > 0) {
		return { kind: "reextract", reasons: validity };
	}
	if (report.report.length === 0) return { kind: "converged" };
	const fresh = freshSteps(report, asked);
	if (fresh.length === 0) return { kind: "stalled" };
	return { kind: "ask", steps: fresh };
}

/** Exit semantics shared by the command's no-UI branch and the driver. */
export function headlessOutcome(hasUI: boolean, action: LoopAction): { exitCode: 0 | 1; write: boolean } {
	if (action.kind === "converged") return { exitCode: 0, write: true };
	// Anything else writes drafts plus report and stops non-zero. In
	// interactive mode the ask/reextract actions continue the loop instead;
	// this function answers only "if we stopped here, how?".
	void hasUI;
	return { exitCode: 1, write: true };
}

/** Fresh-pass extraction prompt: rendered prompts plus answers as context. */
export function buildPassPrompt(args: {
	rendered: Record<string, string>;
	answers: Record<string, string>;
	skillRef: string;
	reextractNote?: string;
	maxPasses: number;
}): string {
	const answerBlock = Object.entries(args.answers)
		.map(([step, answer]) => `Q: ${step}\nA: ${answer}`)
		.join("\n\n");
	return [
		"You are drafting Potato Hamlet law artefacts. Read the project skill before extracting:",
		args.skillRef,
		"",
		"This is one pass of an iterative loop, not a one-shot delivery.",
		...Object.entries(args.rendered).flatMap(([name, text]) => [`--- ${name} prompt ---`, text]),
		"",
		...(answerBlock
			? ["Author answers grounding earlier passes (declare against them, do not re-ask):", "", answerBlock, ""]
			: []),
		...(args.reextractNote ? [`Previous pass refused: ${args.reextractNote}`, ""] : []),
		`Deliver the three draft files plus your report by calling report_ungroundable_steps exactly once.`,
		`Empty report means converged. At most ${args.maxPasses} passes before the loop stops.`,
	].join("\n");
}

/** Gate wrapper verdicts. Execution failure is not a refusal. */
export type GateVerdict =
	| { kind: "pass"; detail: string }
	| { kind: "refused"; findings: string[] }
	| { kind: "execFailed"; error: string };

/** Parse `tools/lawgen/check.py` output: "all checks pass" versus named failures. */
export function parseGateOutput(exitCode: number, stdout: string, stderr: string): GateVerdict {
	const out = `${stdout}\n${stderr}`;
	if (exitCode === 0 && /all checks pass/.test(out)) {
		return { kind: "pass", detail: out.split("\n").filter((l) => l.includes("all checks pass"))[0]?.trim() ?? "all checks pass" };
	}
	const findings = out
		.split("\n")
		.map((l) => l.trim())
		.filter((l) => l.length > 0)
		.slice(0, 12);
	// Negative exit means the script never ran (bad cwd, missing binary):
	// an execution failure, never a refusal, however much stderr it left.
	if (exitCode < 0 || findings.length === 0) {
		return { kind: "execFailed", error: findings.join(" / ").slice(0, 500) || `exit ${exitCode} with no output` };
	}
	return { kind: "refused", findings };
}
