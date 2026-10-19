/** Tool definition glue for report_ungroundable_steps (verified by load). */
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { executeReport } from "./report-core.ts";
import { ReportSchema, ReportToolParams } from "./report-schemas.ts";

export const reportTool = defineTool({
	name: "report_ungroundable_steps",
	label: "Report ungroundable steps",
	description:
		"Hand over one extraction pass: the draft files plus the strict {step, why-ungroundable} " +
		"report. Call exactly once per pass with the full drafts and every step the law text " +
		"requires that no declared object, capability, or action accounts for. An empty report " +
		"means the draft is converged. Free-text uncertainty is not a report — only this call counts.",
	parameters: ReportToolParams,
	outputSchema: ReportSchema,
	async execute(toolCallId, params, _signal, _onUpdate, _ctx) {
		void toolCallId;
		return executeReport(params);
	},
});

export function registerReportTool(pi: ExtensionAPI): void {
	pi.registerTool(reportTool);
}
