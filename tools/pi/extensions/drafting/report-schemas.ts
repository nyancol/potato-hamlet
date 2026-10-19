/**
 * TypeBox schemas pi declares for report_ungroundable_steps.
 *
 * Loaded by pi (typebox is host-provided); deliberately NOT imported by the
 * node self-test. Mirror fidelity against framework/clarification-report.schema.json
 * is asserted textually in pi/selftest/run.ts (required keys, no extras,
 * non-empty strings, top-level report array).
 */
import { Type } from "typebox";

export const ReportEntrySchema = Type.Object(
	{
		step: Type.String({ minLength: 1, description: "Law-text step, quoted closely enough to find in law.txt" }),
		"why-ungroundable": Type.String({
			minLength: 1,
			description: "Which declared object, capability, or action is missing",
		}),
	},
	{ additionalProperties: false },
);

/** Project-owned strict shape; mirrors framework/clarification-report.schema.json. */
export const ReportSchema = Type.Object(
	{ report: Type.Array(ReportEntrySchema) },
	{ additionalProperties: false },
);

export const ReportToolParams = Type.Object(
	{
		ontologyTtl: Type.String({ minLength: 1, description: "ontology.ttl draft content" }),
		rulesLean: Type.String({ minLength: 1, description: "rules.lean draft content" }),
		manifestYaml: Type.String({ minLength: 1, description: "manifest.yaml draft content" }),
		populationTtl: Type.Optional(
			Type.String({ description: "population.ttl draft content, when the pass drafts seeds" }),
		),
		report: ReportSchema,
		passId: Type.Optional(
			Type.String({ minLength: 1, description: "Caller-supplied pass identifier for idempotent receipts" }),
		),
	},
	{ additionalProperties: false },
);
