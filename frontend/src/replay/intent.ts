/**
 * One-shot "start the replay when this case opens" flag, set by the demo and
 * import actions. Module state, not the URL, so reloads and later visits show
 * the finished case with a "Replay run" button instead of replaying.
 */
let pending: string | null = null;

export function requestReplay(caseId: string): void {
  pending = caseId;
}
export function replayRequested(caseId: string): boolean {
  return pending === caseId;
}
export function clearReplayRequest(caseId: string): void {
  if (pending === caseId) pending = null;
}
