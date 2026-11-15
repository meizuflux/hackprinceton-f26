/** Hands a question typed on the mind map to the chat tab, which asks it (and animates the answer) there. */
const queued = new Map<string, string>();
const listeners = new Set<() => void>();

export function queueQuestion(caseId: string, question: string) {
  queued.set(caseId, question);
  listeners.forEach((fn) => fn());
}

export function takeQueuedQuestion(caseId: string): string | undefined {
  const q = queued.get(caseId);
  queued.delete(caseId);
  return q;
}

export function subscribeQueue(fn: () => void) {
  listeners.add(fn);
  return () => void listeners.delete(fn);
}
