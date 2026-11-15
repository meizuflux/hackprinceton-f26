import type { CSSProperties } from "react";
import type { Certainty, Origin } from "../api/types";
import { relationshipKind, type RelationshipKind } from "./relationships";

/**
 * Board color coding. Presentation only: every color is derived from a type or
 * certainty the API supplies, never from layout or guessed meaning.
 *
 * Each card type shares its hue with the thread family that most often meets
 * it (device ↔ communication, location ↔ spatial, event ↔ temporal,
 * person ↔ identity, statement ↔ claim). Contradictions keep the board's red
 * thread. Every ink keeps at least 4.5:1 against the paper card and canvas, and
 * color always travels with an icon, a label, or a line pattern.
 */
export type CardKind = "person" | "device" | "event" | "location" | "statement";
export type ThreadCategory =
  | "communication"
  | "spatial"
  | "temporal"
  | "identity"
  | "claim"
  | "contradicts"
  | "other";

export const CARD_KINDS: CardKind[] = [
  "person",
  "device",
  "event",
  "location",
  "statement",
];
export const THREAD_CATEGORIES: ThreadCategory[] = [
  "communication",
  "spatial",
  "temporal",
  "identity",
  "claim",
  "contradicts",
  "other",
];

/** Ink for text, icons and pushpins; tint is the faint paper wash. */
export const cardColors: Record<
  CardKind | "other",
  { ink: string; tint: string; label: string }
> = {
  person: { ink: "#7b3f8f", tint: "#f4eef3", label: "Person" },
  device: { ink: "#2b5c99", tint: "#edf1f5", label: "Device or account" },
  event: { ink: "#17706a", tint: "#ecf3ef", label: "Event" },
  location: { ink: "#55721c", tint: "#f1f3e6", label: "Location" },
  statement: { ink: "#4d5157", tint: "#f1f0ec", label: "Statement" },
  other: { ink: "#6b5d4f", tint: "#f5f2ea", label: "Other record" },
};

export const threadColors: Record<
  ThreadCategory,
  { ink: string; label: string }
> = {
  communication: { ink: "#2b5c99", label: "Communication" },
  spatial: { ink: "#55721c", label: "Place" },
  temporal: { ink: "#17706a", label: "Time" },
  identity: { ink: "#7b3f8f", label: "Identity" },
  claim: { ink: "#4d5157", label: "Claim" },
  contradicts: { ink: "#b3262f", label: "Contradiction" },
  other: { ink: "#6b5d4f", label: "Other link" },
};

/** Paper surfaces the inks are checked against. */
export const PAPER = { card: "#faf8f1", canvas: "#eee8de" };

export function cardKind(type: string): CardKind | "other" {
  return (CARD_KINDS as string[]).includes(type) ? (type as CardKind) : "other";
}

/** Backend types map to themselves; earlier fixture vocabulary is folded in. */
const legacyThreadTypes: Record<string, ThreadCategory> = {
  assigned_to: "identity",
  associated_with: "identity",
  made_by: "identity",
  logged_at: "spatial",
  covers: "spatial",
  reported_at: "spatial",
  describes: "claim",
  reported_near: "claim",
  time_overlap: "temporal",
  conflicts_with: "contradicts",
  contradiction: "contradicts",
};

export function threadCategory(type: string): ThreadCategory {
  if ((THREAD_CATEGORIES as string[]).includes(type))
    return type as ThreadCategory;
  return legacyThreadTypes[type] ?? "other";
}

/** Inferences and claims stay dashed; claims use a shorter, pencil-like dash. */
export function threadDash(kind: RelationshipKind): string | undefined {
  return kind === "observed" ? undefined : kind === "claim" ? "3 6" : "8 7";
}

/** Short, color-independent wording shown on a thread's label chip. */
export function threadBadge(type: string, certainty?: Certainty) {
  const kind = relationshipKind(type, certainty);
  const category = threadCategory(type);
  if (category === "contradicts")
    return kind === "observed" ? "Contradiction" : "Contradiction · inferred";
  if (kind === "claim") return "Claim";
  if (kind === "inference") return `Inferred ${threadNoun[category]}`;
  return undefined;
}

const threadNoun: Record<ThreadCategory, string> = {
  communication: "contact",
  spatial: "place link",
  temporal: "time link",
  identity: "identity",
  claim: "claim",
  contradicts: "contradiction",
  other: "link",
};

/** CSS custom properties for the board, so CSS and SVG share one source. */
export function boardColorVars(): CSSProperties {
  const vars: Record<string, string> = {};
  for (const [kind, color] of Object.entries(cardColors)) {
    vars[`--card-${kind}`] = color.ink;
    vars[`--card-${kind}-tint`] = color.tint;
  }
  for (const [category, color] of Object.entries(threadColors)) {
    vars[`--thread-${category}`] = color.ink;
  }
  return vars as CSSProperties;
}

function luminance(hex: string) {
  const value = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => {
    const channel = parseInt(value.slice(i, i + 2), 16) / 255;
    return channel <= 0.03928
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(a: string, b: string) {
  const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (high + 0.05) / (low + 0.05);
}

/**
 * Pipeline origin of a card or thread. Origin never changes hue: it is shown
 * by a graphite stamp chip (icon plus word), a hatched strip on the card and
 * the same icon on thread labels. `record` and `rules` stay unmarked so the
 * board is not noisy; the graphite ink is neutral (not red, amber or blue).
 */
export const ORIGIN_INK = "#33373d";
export const MARKED_ORIGINS = ["ml", "agent", "llm"] as const;
export type MarkedOrigin = (typeof MARKED_ORIGINS)[number];

export const originMarks: Record<
  MarkedOrigin,
  { chip: string; label: string; pattern: string }
> = {
  ml: { chip: "ML", label: "Traditional ML", pattern: "dotted" },
  agent: { chip: "Agent", label: "Agent investigator", pattern: "hatched" },
  llm: { chip: "LLM", label: "LLM claim extraction", pattern: "ruled" },
};

export function markedOrigin(origin?: Origin): MarkedOrigin | undefined {
  return (MARKED_ORIGINS as readonly string[]).includes(origin ?? "")
    ? (origin as MarkedOrigin)
    : undefined;
}

/** Full wording for inspectors and tags, including the stage when known. */
export function originLabel(origin?: Origin, stage?: string, method?: string) {
  const base: Record<Origin, string> = {
    record: "Ingested record",
    rules: "Deterministic rules",
    ml: "Traditional ML",
    llm: "LLM claim extraction",
    agent: "Deepagents investigator (Claude)",
  };
  if (!origin) return undefined;
  return [
    base[origin] + (method ? ` (${method})` : ""),
    stage && `stage ${stage}`,
  ]
    .filter(Boolean)
    .join(" · ");
}
