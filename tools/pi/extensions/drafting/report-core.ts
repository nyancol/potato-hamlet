/**
 * report_ungroundable_steps: execute logic plus plain interfaces.
 *
 * No runtime imports beyond ./loop-lib.ts — deliberately NOT typebox: this
 * module must load under plain node for the self-test. The TypeBox schemas
 * pi declares live in report-schemas.ts; the self-test asserts the two
 * mirrors carry the same strictness (required keys, no extras, non-empty).
 *
 * The params carry the three draft files plus the report. population.ttl
 * rides along as an OPTIONAL fourth field: the contract names three drafts,
 * but the gate judges the full artefact set, so a pass that omits seeds
 * would be uncheckable. Seeds are law-derived individuals by reference, per
 * the prompt contract; the tool moves them, it does not author them.
 */

import { createHash } from "node:crypto";
import { validateReport } from "./loop-lib.ts";

export interface ReportEntryInput {
	step: string;
	"why-ungroundable": string;
}

export interface ReportToolArgs {
	ontologyTtl: string;
	rulesLean: string;
	manifestYaml: string;
	populationTtl?: string;
	report: { report: Array<{ step: string; "why-ungroundable": string }> };
	passId?: string;
}

/** Content block shape the host renderer consumes (matching gate tools' convention). */
export interface ContentBlock {
	type: "text";
	text: string;
}

export interface ReportToolOutcome {
	content: ContentBlock[];
	details: {
		drafts: Record<string, string>;
		draftHashes: Record<string, string>;
		entryCount: number;
		converged: boolean;
		/** The report itself, so readers of session tool results need no second lookup. */
		report: Array<{ step: string; "why-ungroundable": string }>;
		passId: string | null;
	};
	structuredContent: { report: Array<{ step: string; "why-ungroundable": string }> };
}

/** SHA256 hex of a string — same algo the gate and freeze scripts use. */
export function sha256hex(text: string): string {
	return createHash("sha256").update(text).digest("hex");
}

/**
 * One scripted-callable handoff. Throws on a malformed pass so pi reports a
 * failed tool result and the model retries; a WELL-FORMED pass always
 * succeeds here — convergence is the command's decision, never the tool's.
 *
 * Content is returned as blocks (never a bare string), matching the gate
 * tools' convention and the host renderer's consumption shape.
 */
export function executeReport(args: ReportToolArgs): ReportToolOutcome {
	for (const [name, text] of [
		["ontologyTtl", args.ontologyTtl],
		["rulesLean", args.rulesLean],
		["manifestYaml", args.manifestYaml],
	] as const) {
		if (typeof text !== "string" || text.trim() === "") {
			throw new Error(`report_ungroundable_steps: draft file ${name} is missing or empty`);
		}
	}
	const violations = validateReport(args.report);
	if (violations.length > 0) {
		throw new Error(`report_ungroundable_steps: strict report rejected: ${violations[0]}`);
	}
	const drafts: Record<string, string> = {
		"ontology.ttl": args.ontologyTtl,
		"rules.lean": args.rulesLean,
		"manifest.yaml": args.manifestYaml,
	};
	if (typeof args.populationTtl === "string") drafts["population.ttl"] = args.populationTtl;
	const draftHashes: Record<string, string> = {};
	for (const [name, text] of Object.entries(drafts)) {
		draftHashes[name] = sha256hex(text);
	}
	const n = args.report.report.length;
	const report = args.report.report.map((e) => ({ step: e.step, "why-ungroundable": e["why-ungroundable"] }));
	const passId = args.passId ?? null;
	const hashLine =
		Object.entries(draftHashes)
			.map(([f, h]) => `  ${f}: sha256=${h}`)
			.join("\n");
	const idLine = passId ? `\npassId: ${passId}` : "";
	const summary =
		n === 0
			? `Report accepted: empty, the loop has converged.${idLine}\nDraft hashes:\n${hashLine}`
			: `Report accepted: ${n} ungroundable step(s): ${report.map((e) => JSON.stringify(e.step)).join("; ")}${idLine}\nDraft hashes:\n${hashLine}`;
	return {
		content: [{ type: "text", text: summary }],
		details: { drafts, draftHashes, entryCount: n, converged: n === 0, report, passId },
		structuredContent: { report },
	};
}
