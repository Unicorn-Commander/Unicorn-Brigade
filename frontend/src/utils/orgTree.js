import { byRankDesc } from './rank';

/**
 * Build the chain-of-command tree from the agent roster.
 *
 * Prefers an explicit `reportsTo` field (to be authored in seed_agents.json,
 * pending owner sign-off). Until that exists it falls back to a rank-aware
 * domain derivation so the chart renders today: within each domain the highest
 * rank leads and reports to the orchestrator; the rest of the domain report to
 * that lead. (Pure domain+rank is flatter than a hand-authored tree — which is
 * exactly why `reportsTo` is worth authoring.)
 *
 * Returns { agents, byId, root, parentOf, childrenById, edgesResting }.
 *
 * Note: lives in utils/ (not lib/) because the repo's .gitignore ignores lib/.
 */
export function buildOrgTree(agents) {
  const list = (Array.isArray(agents) ? agents : []).filter(Boolean);
  const byId = new Map(list.map((a) => [a.id, a]));
  const root =
    list.find((a) => a.type === 'orchestrator') || byId.get('the-general') || list[0] || null;

  const parentOf = new Map(); // childId -> parentId
  const hasReportsTo = list.some((a) => a.reportsTo);

  if (root && hasReportsTo) {
    list.forEach((a) => {
      if (a.id === root.id) return;
      const pid = a.reportsTo && byId.has(a.reportsTo) ? a.reportsTo : root.id;
      parentOf.set(a.id, pid);
    });
  } else if (root) {
    const byDomain = new Map();
    list.forEach((a) => {
      if (a.id === root.id) return;
      const d = (a.domain || 'general').toLowerCase();
      if (!byDomain.has(d)) byDomain.set(d, []);
      byDomain.get(d).push(a);
    });
    byDomain.forEach((members) => {
      const sorted = [...members].sort(byRankDesc);
      const lead = sorted[0];
      parentOf.set(lead.id, root.id);
      sorted.slice(1).forEach((m) => parentOf.set(m.id, lead.id));
    });
  }

  const childrenById = new Map(list.map((a) => [a.id, []]));
  parentOf.forEach((pid, id) => {
    if (childrenById.has(pid)) childrenById.get(pid).push(id);
  });
  childrenById.forEach((kids) =>
    kids.sort((x, y) => byRankDesc(byId.get(x), byId.get(y)))
  );

  const edgesResting = [];
  parentOf.forEach((pid, id) =>
    edgesResting.push({ id: `e-${pid}-${id}`, source: pid, target: id })
  );

  return { agents: list, byId, root, parentOf, childrenById, edgesResting };
}

export default buildOrgTree;
