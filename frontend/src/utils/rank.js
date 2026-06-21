// Military rank helpers for the agent roster.
//
// `RANK_WEIGHT` orders every rank that appears across the 17 seed agents
// (higher = more senior). Used by the org chart to tie-break which agent leads
// a domain and to weight the node ring, and by rank badges. The previous inline
// map in AgentCard only covered 6 of the 13 ranks (everything else defaulted to
// 3 stars), so this is the authoritative ladder.
export const RANK_WEIGHT = {
  'Field Marshal': 13,
  General: 12,
  Colonel: 11,
  'Lieutenant Colonel': 10,
  Commander: 9,
  Major: 8,
  Professor: 8,
  Captain: 7,
  'Chief Warrant Officer': 6,
  Lieutenant: 5,
  'Gunnery Sergeant': 4,
  'Sergeant First Class': 3,
  Sergeant: 2,
  Specialist: 1,
};

export function rankWeight(rank) {
  return RANK_WEIGHT[rank] ?? 0;
}

// Compress the 13-rung ladder into a 1..5 star count for badges.
export function rankStars(rank) {
  const w = rankWeight(rank);
  if (w >= 12) return 5; // Field Marshal, General
  if (w >= 10) return 4; // Colonel, Lieutenant Colonel
  if (w >= 8) return 3; // Commander, Major, Professor
  if (w >= 6) return 2; // Captain, Chief Warrant Officer
  if (w >= 1) return 1; // Lieutenant and below
  return 0;
}

// Sort comparator: most senior first. Stable tie-break by displayName/id.
export function byRankDesc(a, b) {
  const d = rankWeight(b?.rank) - rankWeight(a?.rank);
  if (d !== 0) return d;
  return String(a?.displayName || a?.id || '').localeCompare(String(b?.displayName || b?.id || ''));
}
