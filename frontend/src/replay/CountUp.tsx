import { useEffect, useRef, useState } from "react";
import "./replay.css";

const reducedMotion = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** The number shown `elapsed` ms into a count from `from` to `to` (ease-out). */
export function countFrame(
  from: number,
  to: number,
  elapsed: number,
  duration: number,
): number {
  if (elapsed >= duration || duration <= 0) return to;
  const t = Math.max(0, elapsed) / duration;
  const eased = 1 - (1 - t) ** 3;
  return Math.round(from + (to - from) * eased);
}

/**
 * Counts up to `value` when it rises, so a batch of items arriving at once is
 * seen to add up. It shows the real value at rest; drops are shown at once.
 * Presentation only.
 */
export function useCountUp(value: number, duration = 600): number {
  const [shown, setShown] = useState(value);
  const shownRef = useRef(value);
  shownRef.current = shown;
  useEffect(() => {
    const from = shownRef.current;
    if (value <= from || reducedMotion()) {
      setShown(value);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const next = countFrame(from, value, now - start, duration);
      setShown(next);
      if (next !== value) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, duration]);
  return shown;
}

/** A number that counts up when it rises and briefly highlights the change. */
export function CountUp({
  value,
  duration,
  format = (n) => n.toLocaleString("en-US"),
}: {
  value: number;
  duration?: number;
  format?: (n: number) => string;
}) {
  const shown = useCountUp(value, duration);
  return (
    <span className="count-up" data-counting={shown !== value || undefined}>
      {format(shown)}
    </span>
  );
}
