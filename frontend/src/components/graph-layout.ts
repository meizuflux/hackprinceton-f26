/**
 * Full-graph layout. Presentation only: it returns positions for the cards the
 * API supplies and never adds, removes, merges or reorders evidence.
 */
import {
  getPinDimensions,
  PIN_GAP,
  type PinDimensions,
  type Point,
} from "./board-layout";

type LayoutNode = {
  id: string;
  type: string;
  gapId?: string;
  origin?: string;
  size?: { width: number; height: number };
  media?: { kind: "photo" | "video" };
};

/** Room between connected cards beyond their own half-diagonals. */
const SPRING_SLACK = 70;
/** Space between packed clusters and around the periphery. */
const CLUSTER_GAP = 160;
const ITERATIONS = 360;

type Body = {
  id: string;
  w: number;
  h: number;
  r: number;
  x: number;
  y: number;
};

/**
 * Deterministic force layout of one connected cluster: a radial tree from the
 * best-connected card seeds the positions, springs pull linked cards together,
 * every pair repels, and a final pass pushes overlapping cards apart with the
 * 40px clearance. Returns card centres.
 */
function layoutCluster(
  ids: string[],
  sizes: Map<string, PinDimensions>,
  neighbours: Map<string, string[]>,
): Map<string, Point> {
  const degree = (id: string) => neighbours.get(id)?.length ?? 0;
  const byRank = (a: string, b: string) =>
    degree(b) - degree(a) || a.localeCompare(b);
  const members = new Set(ids);
  const root = [...ids].sort(byRank)[0];

  // Radial tree seed: each subtree gets a wedge proportional to its size.
  const children = new Map<string, string[]>();
  const depth = new Map<string, number>([[root, 0]]);
  const queue = [root];
  while (queue.length) {
    const id = queue.shift()!;
    const next = (neighbours.get(id) ?? [])
      .filter((other) => members.has(other) && !depth.has(other))
      .sort(byRank);
    for (const other of next) depth.set(other, depth.get(id)! + 1);
    children.set(id, next);
    queue.push(...next);
  }
  const weight = new Map<string, number>();
  const weigh = (id: string): number => {
    const total =
      1 +
      (children.get(id) ?? []).reduce((sum, child) => sum + weigh(child), 0);
    weight.set(id, total);
    return total;
  };
  weigh(root);
  const ring = 360;
  const seed = new Map<string, Point>();
  const place = (id: string, from: number, to: number) => {
    const d = depth.get(id)!;
    const angle = (from + to) / 2;
    seed.set(
      id,
      d === 0
        ? { x: 0, y: 0 }
        : {
            x: Math.cos(angle) * ring * d,
            y: Math.sin(angle) * ring * d * 0.75,
          },
    );
    let cursor = from;
    const kids = children.get(id) ?? [];
    const total = kids.reduce((sum, kid) => sum + weight.get(kid)!, 0);
    for (const kid of kids) {
      const span = ((to - from) * weight.get(kid)!) / total;
      place(kid, cursor, cursor + span);
      cursor += span;
    }
  };
  place(root, -Math.PI, Math.PI);

  const bodies: Body[] = ids.map((id) => {
    const { width, height } = sizes.get(id)!;
    const at = seed.get(id)!;
    return {
      id,
      w: width,
      h: height,
      r: Math.hypot(width, height) / 2,
      x: at.x,
      y: at.y,
    };
  });
  const index = new Map(bodies.map((body, i) => [body.id, i]));
  const springs: Array<[number, number]> = [];
  for (const body of bodies)
    for (const other of neighbours.get(body.id) ?? []) {
      const i = index.get(body.id)!;
      const j = index.get(other);
      if (j !== undefined && i < j) springs.push([i, j]);
    }

  const n = bodies.length;
  const dx = new Float64Array(n);
  const dy = new Float64Array(n);
  for (let step = 0; step < ITERATIONS; step++) {
    const heat = 1 - step / ITERATIONS;
    const limit = 6 + 120 * heat;
    dx.fill(0);
    dy.fill(0);
    // Repulsion between nearby cards, scaled to their size.
    for (let i = 0; i < n; i++) {
      const a = bodies[i];
      for (let j = i + 1; j < n; j++) {
        const b = bodies[j];
        let x = a.x - b.x;
        let y = a.y - b.y;
        let d = Math.hypot(x, y);
        if (d < 1) {
          // Coincident seeds part along a fixed, index-based direction.
          x = Math.cos(i * 7 + j);
          y = Math.sin(i * 7 + j);
          d = 1;
        }
        const reach = a.r + b.r + PIN_GAP;
        if (d > reach * 2.5) continue;
        const force = (reach * reach) / d / 7;
        dx[i] += (x / d) * force;
        dy[i] += (y / d) * force;
        dx[j] -= (x / d) * force;
        dy[j] -= (y / d) * force;
      }
    }
    // Springs: linked cards rest just beyond touching. A hub moves less than
    // a leaf, so leaves gather around the card they belong to.
    for (const [i, j] of springs) {
      const a = bodies[i];
      const b = bodies[j];
      const x = b.x - a.x;
      const y = b.y - a.y;
      const d = Math.max(Math.hypot(x, y), 1);
      const rest = a.r + b.r + SPRING_SLACK;
      const force = (d - rest) * 0.35;
      const share = degree(a.id) / (degree(a.id) + degree(b.id));
      dx[i] += (x / d) * force * (1 - share) * 2;
      dy[i] += (y / d) * force * (1 - share) * 2;
      dx[j] -= (x / d) * force * share * 2;
      dy[j] -= (y / d) * force * share * 2;
    }
    for (let i = 0; i < n; i++) {
      // Gentle gravity keeps the cluster compact and a little wider than tall.
      dx[i] -= bodies[i].x * 0.01;
      dy[i] -= bodies[i].y * 0.016;
      const d = Math.hypot(dx[i], dy[i]);
      if (d > limit) {
        dx[i] = (dx[i] / d) * limit;
        dy[i] = (dy[i] / d) * limit;
      }
      bodies[i].x += dx[i];
      bodies[i].y += dy[i];
    }
    if (step > ITERATIONS * 0.6) separate(bodies, 1);
  }
  separate(bodies, 600);
  return new Map(bodies.map((body) => [body.id, { x: body.x, y: body.y }]));
}

/** Pushes overlapping cards apart along their shallower overlap until each keeps the clearance. */
function separate(bodies: Body[], rounds: number) {
  for (let round = 0; round < rounds; round++) {
    let moved = false;
    for (let i = 0; i < bodies.length; i++) {
      for (let j = i + 1; j < bodies.length; j++) {
        const a = bodies[i];
        const b = bodies[j];
        const ox = (a.w + b.w) / 2 + PIN_GAP - Math.abs(a.x - b.x);
        const oy = (a.h + b.h) / 2 + PIN_GAP - Math.abs(a.y - b.y);
        if (ox <= 0 || oy <= 0) continue;
        moved = true;
        if (ox < oy) {
          const push = (ox / 2 + 0.5) * (a.x <= b.x ? -1 : 1);
          a.x += push;
          b.x -= push;
        } else {
          const push = (oy / 2 + 0.5) * (a.y <= b.y ? -1 : 1);
          a.y += push;
          b.y -= push;
        }
      }
    }
    if (!moved) return;
  }
}

/**
 * Presentation-only layout for backend graphs, whose nodes arrive with column
 * placeholders. Cards cluster by connection, not by type: each connected
 * cluster gets a deterministic force layout (so a photo sits by the camera,
 * place or person it is linked to), clusters are packed largest first, and
 * unlinked cards line up in a tidy periphery below. Returns top-left positions.
 */
export function layoutCaseGraph(
  nodes: LayoutNode[],
  edges: Array<{ source: string; target: string }>,
): Map<string, Point> {
  const sizes = new Map(nodes.map((node) => [node.id, getPinDimensions(node)]));
  const types = new Map(nodes.map((node) => [node.id, node.type]));
  const neighbours = new Map<string, string[]>();
  for (const node of nodes) neighbours.set(node.id, []);
  for (const edge of edges) {
    if (edge.source === edge.target) continue;
    const a = neighbours.get(edge.source);
    const b = neighbours.get(edge.target);
    if (!a || !b || a.includes(edge.target)) continue;
    a.push(edge.target);
    b.push(edge.source);
  }

  // Connected clusters, largest first; ties by first card ID for determinism.
  const seen = new Set<string>();
  const clusters: string[][] = [];
  const loners: string[] = [];
  for (const node of nodes) {
    if (seen.has(node.id)) continue;
    const cluster: string[] = [];
    const stack = [node.id];
    seen.add(node.id);
    while (stack.length) {
      const id = stack.pop()!;
      cluster.push(id);
      for (const other of neighbours.get(id)!)
        if (!seen.has(other)) {
          seen.add(other);
          stack.push(other);
        }
    }
    if (cluster.length === 1) loners.push(cluster[0]);
    else clusters.push(cluster.sort());
  }
  clusters.sort((a, b) => b.length - a.length || a[0].localeCompare(b[0]));

  type Block = { width: number; height: number; cards: Map<string, Point> };
  const blocks: Block[] = clusters.map((ids) => {
    const centres = layoutCluster(ids, sizes, neighbours);
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const [id, c] of centres) {
      const { width, height } = sizes.get(id)!;
      minX = Math.min(minX, c.x - width / 2);
      minY = Math.min(minY, c.y - height / 2);
      maxX = Math.max(maxX, c.x + width / 2);
      maxY = Math.max(maxY, c.y + height / 2);
    }
    const cards = new Map<string, Point>();
    for (const [id, c] of centres) {
      const { width, height } = sizes.get(id)!;
      cards.set(id, {
        x: Math.round(c.x - width / 2 - minX),
        y: Math.round(c.y - height / 2 - minY),
      });
    }
    return { width: maxX - minX, height: maxY - minY, cards };
  });

  // The main cluster sits top left; smaller clusters stack in columns to its
  // right, each column no taller than the main cluster.
  const positions = new Map<string, Point>();
  let right = 0;
  let bottom = 0;
  const [main, ...rest] = blocks;
  if (main) {
    for (const [id, p] of main.cards) positions.set(id, p);
    right = main.width;
    bottom = main.height;
  }
  const columnHeight = Math.max(main?.height ?? 0, 900);
  let x = main ? right + CLUSTER_GAP : 0;
  let y = 0;
  let columnWidth = 0;
  for (const block of rest) {
    if (y > 0 && y + block.height > columnHeight) {
      x += columnWidth + CLUSTER_GAP;
      y = 0;
      columnWidth = 0;
    }
    for (const [id, p] of block.cards)
      positions.set(id, { x: x + p.x, y: y + p.y });
    columnWidth = Math.max(columnWidth, block.width);
    right = Math.max(right, x + block.width);
    bottom = Math.max(bottom, y + block.height);
    y += block.height + CLUSTER_GAP;
  }

  // Unlinked cards: a tidy grid along the bottom, by type, then by ID.
  if (loners.length) {
    const order = ["person", "device", "location", "event", "statement"];
    const rank = (id: string) => {
      const index = order.indexOf(types.get(id) ?? "");
      return index < 0 ? order.length : index;
    };
    loners.sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
    const width = Math.max(right, 1600);
    let cx = 0;
    let cy = bottom + CLUSTER_GAP;
    let rowHeight = 0;
    for (const id of loners) {
      const size = sizes.get(id)!;
      if (cx > 0 && cx + size.width > width) {
        cx = 0;
        cy += rowHeight + PIN_GAP;
        rowHeight = 0;
      }
      positions.set(id, { x: cx, y: cy });
      cx += size.width + PIN_GAP;
      rowHeight = Math.max(rowHeight, size.height);
    }
  }
  return positions;
}
