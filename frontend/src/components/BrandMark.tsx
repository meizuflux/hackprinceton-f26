import { useId } from "react";

/**
 * MapleTrace mark: a light chevron behind a glassy blue chevron.
 * Geometry and gradient stops mirror `public/mapletrace-mark.svg`.
 */
export const BRAND_MARK_BACK = "M82 50 32 24H11v10h18l30 16-30 16H11v10h21z";
export const BRAND_MARK_UPPER = "M18 50 68 24h21v10H71L41 50z";
export const BRAND_MARK_LOWER = "M18 50h23l30 16h18v10H68z";

export function BrandMark({
  size = 24,
  title,
  className,
}: {
  size?: number;
  /** Accessible name; omit when adjacent text already names the product. */
  title?: string;
  className?: string;
}) {
  const id = useId().replace(/:/g, "");
  const upper = `${id}-upper`;
  const lower = `${id}-lower`;
  return (
    <svg
      className={className ? `brand-mark ${className}` : "brand-mark"}
      width={Math.round(size * (80 / 56))}
      height={size}
      viewBox="10 22 80 56"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      focusable="false"
    >
      <defs>
        <linearGradient
          id={upper}
          gradientUnits="userSpaceOnUse"
          x1="18"
          y1="50"
          x2="89"
          y2="29"
        >
          <stop offset="0" stopColor="#a4e0ff" />
          <stop offset="0.42" stopColor="#81cdff" />
          <stop offset="0.68" stopColor="#6fc0ff" />
          <stop offset="0.87" stopColor="#48a5fb" />
          <stop offset="1" stopColor="#3b96ee" />
        </linearGradient>
        <linearGradient
          id={lower}
          gradientUnits="userSpaceOnUse"
          x1="18"
          y1="50"
          x2="89"
          y2="71"
        >
          <stop offset="0" stopColor="#9cdcff" />
          <stop offset="0.22" stopColor="#78c6ff" />
          <stop offset="0.36" stopColor="#48a3f6" />
          <stop offset="0.52" stopColor="#3d92e3" />
          <stop offset="0.7" stopColor="#57aff2" />
          <stop offset="0.8" stopColor="#74c7fd" />
          <stop offset="1" stopColor="#7acbff" />
        </linearGradient>
      </defs>
      <path d={BRAND_MARK_BACK} fill="#f4f2ec" />
      <path d={BRAND_MARK_UPPER} fill={`url(#${upper})`} />
      <path d={BRAND_MARK_LOWER} fill={`url(#${lower})`} />
    </svg>
  );
}
