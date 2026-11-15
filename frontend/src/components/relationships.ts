import type { Certainty } from "../api/types";

export type RelationshipKind = "observed" | "claim" | "inference";

/**
 * Claims stay claims; otherwise the API's certainty decides whether a
 * relationship is observed or inferred. Fixture types without certainty keep
 * the earlier vocabulary.
 */
export function relationshipKind(
  type: string,
  certainty?: Certainty,
): RelationshipKind {
  if (["claim", "describes", "reported_near"].includes(type)) return "claim";
  if (certainty === "inferred" || type === "time_overlap") return "inference";
  return "observed";
}

export function relationshipLabel(type: string, certainty?: Certainty) {
  const kind = relationshipKind(type, certainty);
  return kind === "observed"
    ? "Observed link"
    : kind === "claim"
      ? "Claim"
      : "Inference";
}
