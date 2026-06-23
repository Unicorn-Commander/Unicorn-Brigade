import { byRankDesc } from './rank';

/**
 * Owner-confirmed chain of command for the 17 named agents.
 *
 * Authored here as a reviewable constant rather than in seed_agents.json,
 * because the agents table has fixed columns (no `reports_to`) — a seed field
 * wouldn't reach the API without a schema migration + reseed. `buildOrgTree`
 * still *prefers* an agent's `reportsTo` if the API ever provides one, so this
 * promotes cleanly to a backend column later with no UI change.
 */
export const CHAIN_OF_COMMAND = {
  'the-general': null, // Field Marshal — apex
  'col-finance': 'the-general',
  'lt-taxstrat': 'col-finance',
  'maj-devops': 'the-general',
  'cpt-fullstack': 'maj-devops',
  'sgt-cipher': 'maj-devops',
  'code-reviewer': 'cpt-fullstack',
  'prof-datasci': 'the-general',
  'sql-analyst': 'prof-datasci',
  'lt-docanalyst': 'prof-datasci',
  gunny: 'the-general',
  'sgt-scribe': 'gunny',
  'judge-advocate': 'the-general',
  'doc-medresearch': 'the-general',
  'detective-holmes': 'the-general',
  'maj-leadgen': 'the-general',
  'support-agent': 'the-general',
};

/**
 * Build the chain-of-command tree from the agent roster.
 *
 * Per-agent parent precedence:
 *   1. `agent.reportsTo` from the API (future backend column)
 *   2. the authored CHAIN_OF_COMMAND map (today)
 *   3. a rank-aware domain fallback (any agent not covered above, e.g. a new one)
 *
 * Returns { agents, byId, root, parentOf, childrenById, edgesResting }.
 */
export function buildOrgTree(agents) {
  const list = (Array.isArray(agents) ? agents : []).filter(Boolean);
  const byId = new Map(list.map((a) => [a.id, a]));
  const root =
    list.find((a) => a.type === 'orchestrator') || byId.get('the-general') || list[0] || null;

  const parentOf = new Map(); // childId -> parentId
  const unplaced = [];

  list.forEach((a) => {
    if (!root || a.id === root.id) return;
    const authored =
      a.reportsTo ?? (a.id in CHAIN_OF_COMMAND ? CHAIN_OF_COMMAND[a.id] : undefined);
    if (authored === undefined) {
      unplaced.push(a);
    } else {
      parentOf.set(a.id, authored && byId.has(authored) ? authored : root.id);
    }
  });

  // Rank-aware domain fallback for anyone not in the authored map.
  if (root && unplaced.length) {
    const byDomain = new Map();
    unplaced.forEach((a) => {
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
  childrenById.forEach((kids) => kids.sort((x, y) => byRankDesc(byId.get(x), byId.get(y))));

  const edgesResting = [];
  parentOf.forEach((pid, id) =>
    edgesResting.push({ id: `e-${pid}-${id}`, source: pid, target: id })
  );

  return { agents: list, byId, root, parentOf, childrenById, edgesResting };
}

export default buildOrgTree;
