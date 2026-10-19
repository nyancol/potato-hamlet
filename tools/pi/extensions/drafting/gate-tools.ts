/** Tool definition glue for the hamlet gate wrappers (verified by load). */
import { Type } from "typebox";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { runHamletBuild, runHamletCheck, runHamletFreeze } from "./gate-core.ts";

const CaseParams = Type.Object(
	{ caseDir: Type.String({ description: "Case directory, e.g. cases/mayor-2027" }) },
	{ additionalProperties: false },
);

function verdictContent(tool: string, verdict: { kind: string; detail?: string; findings?: string[]; error?: string }): string {
	if (verdict.kind === "pass") return `${tool}: PASS — ${verdict.detail ?? ""}`;
	if (verdict.kind === "refused") {
		return `${tool}: REFUSED —\n${(verdict.findings ?? []).map((f) => `  ${f}`).join("\n")}`;
	}
	return `${tool}: EXECUTION FAILED — ${verdict.error ?? "unknown"}`;
}

export const gateTools = [
	defineTool({
		name: "hamlet_check",
		label: "Hamlet check",
		description:
			"Run the repo's own review gate (tools/lawgen/check.py, schema checks over the world fixture) " +
			"on a case directory. A refusal names the finding; an execution failure is a broken " +
			"environment, never a refused draft.",
		parameters: Type.Object(
			{
				caseDir: Type.String({ description: "Case directory, e.g. cases/mayor-2027" }),
				full: Type.Optional(Type.Boolean({ description: "Full gate incl. Lean and oracle (slow). Default schema-only." })),
			},
			{ additionalProperties: false },
		),
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			const verdict = runHamletCheck(params.caseDir, { repoRoot: ctx.cwd }, params.full ?? false);
			if (verdict.kind === "execFailed") throw new Error(verdictContent("hamlet_check", verdict));
			return {
				content: [{ type: "text", text: verdictContent("hamlet_check", verdict) }],
				details: { verdict },
				isError: verdict.kind === "refused",
			};
		},
	}),
	defineTool({
		name: "hamlet_build",
		label: "Hamlet build",
		description:
			"Build the compiled oracle for a case via tools/lawgen/build_oracle.py. Needs the Lean toolchain.",
		parameters: CaseParams,
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			const verdict = runHamletBuild(params.caseDir, { repoRoot: ctx.cwd });
			if (verdict.kind === "execFailed") throw new Error(verdictContent("hamlet_build", verdict));
			return {
				content: [{ type: "text", text: verdictContent("hamlet_build", verdict) }],
				details: { verdict },
				isError: verdict.kind === "refused",
			};
		},
	}),
	defineTool({
		name: "hamlet_freeze",
		label: "Hamlet freeze verify",
		description:
			"Verify a frozen artefact set via tools/lawgen/freeze.py --verify: exit 0 iff frozen and " +
			"unchanged, naming what moved otherwise.",
		parameters: CaseParams,
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			const verdict = runHamletFreeze(params.caseDir, { repoRoot: ctx.cwd });
			if (verdict.kind === "execFailed") throw new Error(verdictContent("hamlet_freeze", verdict));
			return {
				content: [{ type: "text", text: verdictContent("hamlet_freeze", verdict) }],
				details: { verdict },
				isError: verdict.kind === "refused",
			};
		},
	}),
];

export function registerGateTools(pi: ExtensionAPI): void {
	for (const tool of gateTools) pi.registerTool(tool);
}
