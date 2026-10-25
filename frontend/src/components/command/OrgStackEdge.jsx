import { memo } from 'react';
import { BaseEdge } from '@xyflow/react';

const RADIUS = 6;

/**
 * A polyline with rounded corners, as an SVG path. Consecutive points must be
 * axis-aligned (the layout guarantees it).
 */
function roundedPath(points, r = RADIUS) {
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 1; i < points.length - 1; i += 1) {
    const prev = points[i - 1];
    const cur = points[i];
    const next = points[i + 1];
    const inLen = Math.hypot(cur.x - prev.x, cur.y - prev.y);
    const outLen = Math.hypot(next.x - cur.x, next.y - cur.y);
    const rr = Math.min(r, inLen / 2, outLen / 2);
    if (rr <= 0) {
      d += ` L ${cur.x} ${cur.y}`;
      continue;
    }
    const ax = cur.x - Math.sign(cur.x - prev.x) * rr;
    const ay = cur.y - Math.sign(cur.y - prev.y) * rr;
    const bx = cur.x + Math.sign(next.x - cur.x) * rr;
    const by = cur.y + Math.sign(next.y - cur.y) * rr;
    d += ` L ${ax} ${ay} Q ${cur.x} ${cur.y} ${bx} ${by}`;
  }
  const last = points[points.length - 1];
  return `${d} L ${last.x} ${last.y}`;
}

/**
 * The bracket edge of a stacked column: down from the parent to a horizontal
 * bus, across to the column's spine, down the spine to the leaf's row, and
 * into the leaf's left side. Leaves in one column share the bus and the spine,
 * so the overlapping segments read as a single bracket.
 */
function OrgStackEdge({ sourceX, sourceY, targetX, targetY, data, style, markerEnd, interactionWidth }) {
  const busY = data?.busY ?? (sourceY + targetY) / 2;
  const spineX = data?.spineX ?? targetX - 10;
  const points = [
    { x: sourceX, y: sourceY },
    { x: sourceX, y: busY },
    { x: spineX, y: busY },
    { x: spineX, y: targetY },
    { x: targetX, y: targetY },
  ];
  return <BaseEdge path={roundedPath(points)} style={style} markerEnd={markerEnd} interactionWidth={interactionWidth} />;
}

export default memo(OrgStackEdge);
