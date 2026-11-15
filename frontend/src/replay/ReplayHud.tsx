import {
  ChevronDown,
  Pause,
  Play,
  RotateCcw,
  SkipForward,
  Activity,
} from "lucide-react";
import { useEffect, useState } from "react";
import type { ReplayState } from "./useReplay";

/** Fired on `window` when the run panel opens or collapses. */
export const RUN_PANEL_EVENT = "mapletrace:run-panel";
import { CountUp } from "./CountUp";
import {
  describeEvent,
  feedRows,
  formatCost,
  formatDuration,
  formatSpeed,
  formatTokens,
  phaseOrder,
  speeds,
  type Pace,
} from "./trace";
import "./replay.css";

const FEED_LIMIT = 60;

function timingLabel(replay: ReplayState) {
  if (replay.timing === "live") return "live timing";
  if (replay.timing === "estimated") return "estimated (from token counts)";
  return "recorded";
}

const phaseLabel = (pace: Pace) =>
  phaseOrder.find((x) => x.id === pace.phase)?.label ?? pace.phase;

/** States plainly when the replay runs slower or faster than the chosen speed. */
function paceNote(pace: Pace | undefined, speed: number): string {
  if (!pace)
    return speed > 1
      ? "Model waits are shortened; every event is shown"
      : "Recorded waits shown in full";
  if (pace.kind === "slowed")
    return pace.speed >= 0.1
      ? `${phaseLabel(pace)} shown at ${formatSpeed(pace.speed)} so each step is visible`
      : `${phaseLabel(pace)} took ${Math.round(pace.realMs)} ms; slowed so each step is visible`;
  return `Skipping model wait: ${Math.round(pace.realMs / 1000)} s of waiting shown at ${formatSpeed(pace.realMs / pace.wallMs)}`;
}

/** Floating run panel on the mind map: phases, counters, cost and an event feed. */
export function ReplayHud({ replay }: { replay: ReplayState }) {
  // A finished run opens as the compact "Run summary" chip so it never crowds the board; it stays open while a run
  // plays, and can always be expanded.
  const [expanded, setExpanded] = useState(
    () =>
      !replay.finished &&
      (typeof window === "undefined" ||
        !window.matchMedia("(max-width: 900px)").matches),
  );
  const [dismissedFinish, setDismissedFinish] = useState(false);
  const { progress: p } = replay;
  const live = replay.timing === "live" && replay.status === "processing";
  const open = expanded && !(replay.finished && dismissedFinish);
  // The story view leaves room for this panel; tell the board when it opens or closes so it can refit.
  useEffect(() => {
    window.dispatchEvent(new Event(RUN_PANEL_EVENT));
  }, [open]);
  const title = live
    ? "Live run"
    : replay.finished
      ? "Run summary"
      : "Replay of recorded run";

  // Collapse to the summary chip once the run is over, whether it was watched or opened after it finished.
  const [wasFinished, setWasFinished] = useState(replay.finished);
  if (replay.finished !== wasFinished) {
    setWasFinished(replay.finished);
    if (replay.finished) setExpanded(false);
    if (!replay.finished) {
      setExpanded(true);
      setDismissedFinish(false);
    }
  }

  const summary = `${formatCost(p.costUsd)} · ${formatDuration(replay.endMs)}`;
  if (!open) {
    return (
      <button
        type="button"
        className="replay-chip"
        aria-expanded={false}
        aria-controls="replay-hud"
        onClick={() => {
          setExpanded(true);
          setDismissedFinish(false);
        }}
      >
        <Activity size={14} aria-hidden="true" />
        <span>{replay.finished ? "Run summary" : title}</span>
        <strong>{summary}</strong>
      </button>
    );
  }

  const feed = feedRows(replay.shown, FEED_LIMIT);
  const counters: Array<[string, number]> = [
    ["Files", p.filesParsed || p.filesHashed],
    ["Records", p.records],
    ["Entities", p.entities],
    ["ML signals", p.mlSignals],
    ["LLM calls", p.llmCalls],
    ["Tool calls", p.toolCalls],
    ["Agent insights", p.insights],
  ];
  const recordTypes = Object.entries(p.recordTypes).sort((a, b) => b[1] - a[1]);
  const percent = replay.endMs
    ? Math.min(100, (replay.clockMs / replay.endMs) * 100)
    : 0;

  return (
    <aside
      className="replay-hud"
      id="replay-hud"
      aria-label={title}
      data-live={live}
    >
      <header className="replay-hud-header">
        <div>
          <h2>{title}</h2>
          <span className="replay-badge" data-timing={replay.timing}>
            Timing: {timingLabel(replay)}
          </span>
        </div>
        <button
          type="button"
          className="icon-button"
          aria-label="Collapse run panel"
          onClick={() => {
            setExpanded(false);
            setDismissedFinish(true);
          }}
        >
          <ChevronDown size={16} aria-hidden="true" />
        </button>
      </header>

      {live ? (
        <p className="replay-clock">
          Running now · {formatDuration(replay.clockMs)} elapsed
        </p>
      ) : (
        <>
          <p className="replay-clock">
            Recorded run {formatDuration(replay.endMs)} ·{" "}
            {replay.finished ? "finished" : `playing at ${replay.speed}×`}
            <br />
            {!replay.finished && (
              <em className="replay-slowed" data-pace={replay.pace?.kind}>
                {paceNote(replay.pace, replay.speed)}
                <br />
              </em>
            )}
            <span>
              Replay clock {formatDuration(replay.clockMs)} · watched for{" "}
              {formatDuration(replay.wallMs)}
            </span>
          </p>
          <div
            className="replay-bar"
            role="progressbar"
            aria-label="Replay position"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(percent)}
          >
            <span style={{ width: `${percent}%` }} />
          </div>
          <div className="replay-controls">
            <button
              type="button"
              className="text-button"
              onClick={replay.togglePlaying}
            >
              {replay.finished ? (
                <>
                  <RotateCcw size={14} aria-hidden="true" /> Replay run
                </>
              ) : replay.playing ? (
                <>
                  <Pause size={14} aria-hidden="true" /> Pause
                </>
              ) : (
                <>
                  <Play size={14} aria-hidden="true" /> Play
                </>
              )}
            </button>
            <div className="replay-speeds" role="group" aria-label="Speed">
              {speeds.map((s) => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={replay.speed === s}
                  onClick={() => replay.setSpeed(s)}
                >
                  {s}×
                </button>
              ))}
            </div>
            <button
              type="button"
              className="text-button"
              disabled={replay.finished}
              onClick={replay.skipToEnd}
            >
              <SkipForward size={14} aria-hidden="true" /> Skip to end
            </button>
          </div>
        </>
      )}

      <ol className="replay-phases" aria-label="Run phases">
        {phaseOrder.map(({ id, label }) => {
          const phase = p.phases[id];
          return (
            <li key={id} data-status={phase.status}>
              <span>{label}</span>
              <small>
                {phase.status === "done"
                  ? formatDuration(phase.durationMs ?? 0)
                  : phase.status === "running"
                    ? "running"
                    : "waiting"}
              </small>
            </li>
          );
        })}
      </ol>

      <dl className="replay-counters">
        {counters.map(([name, value]) => (
          <div key={name}>
            <dt>{name}</dt>
            <dd>
              <CountUp
                value={value}
                duration={name === "Agent insights" ? 700 : 350}
              />
            </dd>
          </div>
        ))}
      </dl>
      {recordTypes.length > 0 && (
        <p className="replay-types">
          {recordTypes.map(([name, count]) => `${name} ${count}`).join(" · ")}
        </p>
      )}

      <div className="replay-cost" aria-label="Model usage">
        <span>
          {formatTokens(p.inputTokens)} in · {formatTokens(p.outputTokens)} out
        </span>
        <strong>{formatCost(p.costUsd)}</strong>
      </div>

      <ol className="replay-feed" role="log" aria-label="Run events">
        {feed.map(({ event, count }) => (
          <li key={event.seq} data-phase={event.phase}>
            <time>{formatDuration(event.tMs)}</time>
            {describeEvent(event)}
            {count > 1 && <span className="replay-feed-count">×{count}</span>}
          </li>
        ))}
      </ol>
    </aside>
  );
}
