export type RelationshipKind = "observed" | "claim" | "inference";

/** Existing presentation vocabulary; the API supplies each relationship type. */
export function relationshipKind(type: string): RelationshipKind {
  if (type === "time_overlap") return "inference";
  if (["claim", "describes", "reported_near"].includes(type)) return "claim";
  return "observed";
}

export function relationshipLabel(type: string) {
  const kind = relationshipKind(type);
  return kind === "observed"
    ? "Observed link"
    : kind === "claim"
      ? "Claim"
      : "Inference";
}
