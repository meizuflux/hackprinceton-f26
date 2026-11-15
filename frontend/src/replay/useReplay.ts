import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import { isApiError } from "../api/http";
import type { TraceEvent, TracePage } from "../api/types";
import { clearReplayRequest, replayRequested } from "./intent";
import {
  advanceClock,
  countUpTo,
  defaultSpeed,
  mergeEvents,
  runEndMs,
  summarize,
  type TraceProgress,
} from "./trace";

const POLL_MS = 700;

export type ReplayMode = "none" | "replay" | "live";

export interface ReplayState {
  /** `none`: no trace (mock adapter or no trace for the case); the board shows as usual. */
  mode: ReplayMode;
  /** The trace is still being fetched for a case that asked to replay: keep the board empty. */
  loading: boolean;
  /** The trace is loaded and the board should be filtered to the clock. */
  filtering: boolean;
  timing: TracePage["timing"] | null;
  status: TracePage["status"] | null;
  events: TraceEvent[];
  /** Events the clock has reached. */
  shown: TraceEvent[];
  progress: TraceProgress;
  clockMs: number;
  endMs: number;
  /** Wall-clock seconds spent playing so far. */
  wallMs: number;
  playing: boolean;
  speed: number;
  /** The run (and, for live, the job) is over and the clock reached its end. */
  finished: boolean;
  /** Increments when the run completes while being watched. */
  completedWatching: boolean;
  setSpeed: (speed: number) => void;
  togglePlaying: () => void;
  skipToEnd: () => void;
  restart: () => void;
}

/**
 * Plays a case's recorded run on the replay clock (or follows a live run) and
 * exposes what the clock has reached. Presentation only.
 */
export function useReplay(caseId: string, enabled = true): ReplayState {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [meta, setMeta] = useState<{
    timing: TracePage["timing"];
    status: TracePage["status"];
  } | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [unavailable, setUnavailable] = useState(!enabled);
  const [autoplay, setAutoplay] = useState(() => replayRequested(caseId));
  const [clockMs, setClockMs] = useState(0);
  const [wallMs, setWallMs] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(defaultSpeed);
  const [watched, setWatched] = useState(false);
  const nextRef = useRef(0);
  const heldRef = useRef<TraceEvent[]>([]);

  // Fetch the trace; keep polling while the job runs.
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    nextRef.current = 0;
    heldRef.current = [];
    let firstPage = true;
    let failures = 0;
    const wantsReplay = replayRequested(caseId);
    const poll = async () => {
      try {
        const page = await api.getTrace(caseId, nextRef.current);
        if (cancelled) return;
        if (!page) {
          setUnavailable(true);
          setLoaded(true);
          return;
        }
        nextRef.current = page.next;
        heldRef.current = mergeEvents(heldRef.current, page.events);
        setEvents(heldRef.current);
        setMeta({ timing: page.timing, status: page.status });
        setUnavailable(false);
        if (firstPage) {
          firstPage = false;
          if (page.status === "processing" || wantsReplay) {
            setAutoplay(true);
            setPlaying(true);
          } else {
            // Opened later: show the finished run; "Replay run" starts it again.
            setClockMs(runEndMs(heldRef.current));
          }
          clearReplayRequest(caseId);
        }
        setLoaded(true);
        if (page.status === "processing") timer = setTimeout(poll, POLL_MS);
      } catch (error) {
        if (cancelled) return;
        failures += 1;
        if (
          !heldRef.current.length &&
          (isApiError(error, "not_found") || failures > 3)
        ) {
          setUnavailable(true);
          setLoaded(true);
        } else timer = setTimeout(poll, POLL_MS * 2);
      }
    };
    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [caseId, enabled]);

  const live = meta?.timing === "live" && meta.status === "processing";
  const processing = meta?.status === "processing";
  const lastEventMs = events.at(-1)?.tMs ?? 0;
  const endMs = useMemo(() => runEndMs(events), [events]);
  const capMs = processing ? lastEventMs : endMs;

  // Animation frame clock.
  const clockRef = useRef(0);
  clockRef.current = clockMs;
  useEffect(() => {
    if (!playing || live) return;
    let frame = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = now - last;
      last = now;
      setClockMs((t) => advanceClock(t, dt, speed, capMs));
      setWallMs((w) => w + dt);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, live, speed, capMs]);

  const effectiveClock = live ? lastEventMs : clockMs;
  const reachedEnd =
    !processing && loaded && events.length > 0 && effectiveClock >= endMs;

  // Stop and mark completion when a watched run reaches its end.
  useEffect(() => {
    if (!reachedEnd) return;
    if (playing) {
      setPlaying(false);
      setWatched(true);
    }
  }, [reachedEnd, playing]);

  const count = countUpTo(events, effectiveClock);
  const shown = useMemo(() => events.slice(0, count), [events, count]);
  const progress = useMemo(() => summarize(shown), [shown]);

  const restart = useCallback(() => {
    setClockMs(0);
    setWallMs(0);
    setWatched(false);
    setAutoplay(true);
    setPlaying(true);
  }, []);

  const mode: ReplayMode =
    unavailable || !enabled
      ? "none"
      : meta?.timing === "live"
        ? "live"
        : "replay";
  return {
    mode,
    loading: enabled && !loaded && autoplay,
    filtering: mode !== "none" && (loaded || autoplay),
    timing: meta?.timing ?? null,
    status: meta?.status ?? null,
    events,
    shown,
    progress,
    clockMs: effectiveClock,
    endMs,
    wallMs,
    playing: playing || live,
    speed,
    finished: reachedEnd,
    completedWatching: watched,
    setSpeed,
    togglePlaying: () => {
      if (reachedEnd) restart();
      else setPlaying((p) => !p);
    },
    skipToEnd: () => {
      setClockMs(capMs);
      if (!processing) setPlaying(false);
    },
    restart,
  };
}
