/** Potato Hamlet drafting extension: loop owned as code. */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { registerDraftLaw } from "./draft-law.ts";
import { registerGateTools } from "./gate-tools.ts";
import { registerReportTool } from "./report-tool.ts";
import { registerSettleGuard } from "./settle-guard.ts";

export default function (pi: ExtensionAPI): void {
	registerReportTool(pi);
	registerGateTools(pi);
	registerDraftLaw(pi);
	registerSettleGuard(pi);
}
