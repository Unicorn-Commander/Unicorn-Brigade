import { byRankDesc } from './rank';

/**
 * LEGACY chain of command for the original 17 named agents.
 *
 * Superseded by `agents.reports_to`, which the API now serves as `reportsTo` on
 * every roster record — the hierarchy is stated in the registry alongside rank,
 * title and avatar rather than authored in a UI constant. Kept only as the
 * fallback for a roster served by a Brigade too old to carry the column, and
 * consulted strictly after the server's answer.
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
 *   1. `agent.reportsTo` from the API (agents.reports_to — the stated hierarchy)
 *   2. the legacy CHAIN_OF_COMMAND map (pre-column Brigades)
 *   3. a rank-aware domain fallback (any agent not covered above, e.g. a new one)
 *
 * Returns { agents, byId, root, parentOf, childrenById, edgesResting }.
 */
export function buildOrgTree(agents) {
  const list = (Array.isArray(agents) ? agents : []).filter(Boolean);
  const byId = new Map(list.map((a) => [a.id, a]));

  // Root selection has to follow the SAME source as parentage, or the chart
  // contradicts itself: picking the first `type === 'orchestrator'` row (the
  // roster arrives ordered by domain, so that was whoever sorted first — for
  // the current roster, an agent in the "general" domain) while parenting
  // everyone by `reportsTo` hangs the real apex under an impostor. So when the
  // server states a hierarchy, walk UP a stated line to its top and use that.
  const stated = list.filter((a) => a.reportsTo && byId.has(a.reportsTo));
  let root = null;
  if (stated.length) {
    const seen = new Set();
    let cursor = stated[0];
    while (cursor && cursor.reportsTo && byId.has(cursor.reportsTo) && !seen.has(cursor.id)) {
      seen.add(cursor.id);
      cursor = byId.get(cursor.reportsTo);
    }
    root = cursor || null;
  }
  if (!root) {
    root =
      list.find((a) => a.type === 'orchestrator') || byId.get('the-general') || list[0] || null;
  }

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
