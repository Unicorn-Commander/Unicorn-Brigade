import { useMemo } from 'react';

// Must match the rendered node box in OrgAgentNode — the layout reserves space
// from these numbers, so a node wider than declared overlaps its neighbours.
export const ORG_NODE_W = 248;
export const ORG_NODE_H = 84;

// Geometry of the chart. Siblings with their own reports fan out horizontally;
// leaves (and collapsed teams) under one parent stack into short columns, the
// way a printed org chart does it — that is what keeps 57 agents on one screen.
const H_GAP = 24; // between sibling subtrees
const V_GAP = 64; // between ranks
const STACK_GUTTER = 20; // room for the bracket spine left of a stacked column
const STACK_COL_GAP = 16; // between stacked columns
const STACK_ROW_GAP = 24; // between stacked rows (leaves may carry a toggle pill)
const MAX_ROWS = 5; // rows per stacked column before a new column starts

/**
 * Lay out a chain-of-command tree.
 *
 *   rfNodes  xyflow nodes in chain-of-command order (apex first, then each
 *            parent's rank-sorted reports, depth first) — sibling order is
 *            taken from this array
 *   rfEdges  resting parent -> child edges (source = parent)
 *
 * Returns { nodes, edges }: nodes with absolute positions and handle sides,
 * edges typed `smoothstep` (fan-out) or `orgStack` (bracket into a stacked
 * column) with the handle ids and the bracket geometry each needs.
 * Pure and synchronous — recompute only when the visible set changes.
 */
export function layoutOrgChart(rfNodes, rfEdges) {
  if (!rfNodes.length) return { nodes: [], edges: [] };
  const index = new Map(rfNodes.map((n, i) => [n.id, i]));
  const children = new Map(rfNodes.map((n) => [n.id, []]));
  const hasParent = new Set();
  for (const e of rfEdges) {
    if (!children.has(e.source) || !children.has(e.target) || e.source === e.target) continue;
    children.get(e.source).push(e.target);
    hasParent.add(e.target);
  }
  children.forEach((kids) => kids.sort((a, b) => index.get(a) - index.get(b)));

  // Measure: each subtree is a rectangle of `width`; its children are slots —
  // either a branch subtree or one stack of leaves.
  const measure = (id) => {
    const kids = children.get(id) || [];
    const branches = kids.filter((k) => (children.get(k) || []).length > 0);
    let leaves = kids.filter((k) => (children.get(k) || []).length === 0);
    // A single leaf hangs below like a branch; two or more stack.
    if (leaves.length === 1) {
      branches.push(leaves[0]);
      branches.sort((a, b) => index.get(a) - index.get(b));
      leaves = [];
    }
    const slots = branches.map(measure);
    if (leaves.length) {
      const cols = Math.ceil(leaves.length / MAX_ROWS);
      const rows = Math.ceil(leaves.length / cols);
      slots.push({
        stack: true,
        leaves,
        cols,
        rows,
        width: cols * (STACK_GUTTER + ORG_NODE_W) + (cols - 1) * STACK_COL_GAP,
      });
    }
    const childrenWidth = slots.reduce((s, sl) => s + sl.width, 0) + Math.max(0, slots.length - 1) * H_GAP;
    return { id, slots, childrenWidth, width: Math.max(ORG_NODE_W, childrenWidth) };
  };

  const placed = new Map(); // id -> { x, y, side, spineX?, busY? }
  const place = (t, left, y) => {
    placed.set(t.id, { x: left + t.width / 2 - ORG_NODE_W / 2, y, side: 'top' });
    const childY = y + ORG_NODE_H + V_GAP;
    const busY = y + ORG_NODE_H + V_GAP / 2;
    let x = left + (t.width - t.childrenWidth) / 2;
    for (const slot of t.slots) {
      if (slot.stack) {
        slot.leaves.forEach((leaf, i) => {
          const col = Math.floor(i / slot.rows);
          const row = i % slot.rows;
          const colLeft = x + col * (STACK_GUTTER + ORG_NODE_W + STACK_COL_GAP);
          placed.set(leaf, {
            x: colLeft + STACK_GUTTER,
            y: childY + row * (ORG_NODE_H + STACK_ROW_GAP),
            side: 'left',
            spineX: colLeft + STACK_GUTTER / 2,
            busY,
          });
        });
      } else {
        place(slot, x, childY);
      }
      x += slot.width + H_GAP;
    }
  };

  // Roots: the apex, plus anyone the edges never reach (a line mid-edit) —
  // laid out side by side rather than dropped off the board.
  let left = 0;
  for (const n of rfNodes) {
    if (hasParent.has(n.id) || placed.has(n.id)) continue;
    const t = measure(n.id);
    place(t, left, 0);
    left += t.width + H_GAP * 2;
  }

  const nodes = rfNodes.map((n) => {
    const p = placed.get(n.id) || { x: 0, y: 0, side: 'top' };
    return {
      ...n,
      position: { x: p.x, y: p.y },
      // Declared, not measured: the box is fixed, and xyflow's minimap only
      // draws nodes whose user object carries dimensions.
      width: ORG_NODE_W,
      height: ORG_NODE_H,
      targetPosition: p.side,
      sourcePosition: 'bottom',
    };
  });
  const edges = rfEdges
    .filter((e) => placed.has(e.source) && placed.has(e.target))
    .map((e) => {
      const p = placed.get(e.target);
      return p.side === 'left'
        ? { ...e, type: 'orgStack', sourceHandle: 'bottom', targetHandle: 'left', data: { spineX: p.spineX, busY: p.busY } }
        : { ...e, type: 'smoothstep', sourceHandle: 'bottom', targetHandle: 'top', pathOptions: { borderRadius: 6 } };
    });
  return { nodes, edges };
}

/** Memoized layoutOrgChart for xyflow; recomputes only when the visible set changes. */
export function useOrgLayout(rfNodes, rfEdges) {
  return useMemo(() => layoutOrgChart(rfNodes, rfEdges), [rfNodes, rfEdges]);
}

export default useOrgLayout;
