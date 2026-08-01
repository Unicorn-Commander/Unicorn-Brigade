import { useMemo } from 'react';
import dagre from '@dagrejs/dagre';

// Must match the rendered node box in OrgAgentNode — dagre reserves space from
// these numbers, so a node that is wider than declared overlaps its neighbours.
export const ORG_NODE_W = 236;
export const ORG_NODE_H = 92;

/**
 * Run dagre top-to-bottom over the given xyflow nodes/edges and return the nodes
 * with absolute positions. Dagre owns x/y so live edges never trigger relayout;
 * recompute only when the visible node/edge set changes.
 */
export function useOrgLayout(rfNodes, rfEdges, opts = {}) {
  const { rankdir = 'TB', ranksep = 100, nodesep = 44 } = opts;
  return useMemo(() => {
    if (!rfNodes.length) return rfNodes;
    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir, ranksep, nodesep, marginx: 32, marginy: 32 });
    rfNodes.forEach((n) => g.setNode(n.id, { width: ORG_NODE_W, height: ORG_NODE_H }));
    rfEdges.forEach((e) => g.setEdge(e.source, e.target));
    dagre.layout(g);
    return rfNodes.map((n) => {
      const p = g.node(n.id);
      return {
        ...n,
        position: { x: p.x - ORG_NODE_W / 2, y: p.y - ORG_NODE_H / 2 },
        targetPosition: 'top',
        sourcePosition: 'bottom',
      };
    });
  }, [rfNodes, rfEdges, rankdir, ranksep, nodesep]);
}

export default useOrgLayout;
