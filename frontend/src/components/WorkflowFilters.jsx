/**
 * WorkflowFilters — the templates toolbar: search, tag, complexity, sort and
 * the grid/list toggle, in one Card. Every control has an accessible name.
 */
import { Search, LayoutGrid, List } from 'lucide-react';
import { DOMAIN_TAGS } from './WorkflowCard';
import { Button, Card, Input, Select, Tabs } from './ui';

export const SORTS = [
  ['newest', 'Newest first'],
  ['name-asc', 'Name A–Z'],
  ['name-desc', 'Name Z–A'],
  ['steps-asc', 'Fewest steps'],
  ['steps-desc', 'Most steps'],
];

export default function WorkflowFilters({ query, onQuery, tag, onTag, complexity, onComplexity, sort, onSort, view, onView, tags = [], resultCount, totalCount, onClear }) {
  const hasFilters = Boolean(query || tag || complexity);
  const domainTags = tags.filter((t) => DOMAIN_TAGS.includes(t));
  const otherTags = tags.filter((t) => !DOMAIN_TAGS.includes(t));

  return (
    <Card padding="sm" className="mb-5">
      <div className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_auto_auto_auto_auto]">
        <div className="relative">
          <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input type="search" aria-label="Search workflows" placeholder="Search workflows, tags…" value={query} onChange={(e) => onQuery(e.target.value)} className="pl-9" />
        </div>
        <Select aria-label="Filter by tag" value={tag} onChange={(e) => onTag(e.target.value)} className="md:w-44">
          <option value="">All tags</option>
          {domainTags.length > 0 && (
            <optgroup label="Domains">
              {domainTags.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </optgroup>
          )}
          {otherTags.length > 0 && (
            <optgroup label="Other tags">
              {otherTags.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </optgroup>
          )}
        </Select>
        <Select aria-label="Filter by complexity" value={complexity} onChange={(e) => onComplexity(e.target.value)} className="md:w-44">
          <option value="">Any complexity</option>
          <option value="simple">Simple (≤3 steps)</option>
          <option value="moderate">Moderate (4–5 steps)</option>
          <option value="complex">Complex (6+ steps)</option>
        </Select>
        <Select aria-label="Sort workflows" value={sort} onChange={(e) => onSort(e.target.value)} className="md:w-40">
          {SORTS.map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </Select>
        <Tabs
          variant="segmented"
          size="sm"
          label="Layout"
          idBase="wf-view"
          value={view}
          onChange={onView}
          tabs={[
            { id: 'grid', label: 'Grid', icon: LayoutGrid },
            { id: 'list', label: 'List', icon: List },
          ]}
          className="self-center"
        />
      </div>
      {typeof resultCount === 'number' && typeof totalCount === 'number' && (hasFilters || resultCount !== totalCount) && (
        <div className="mt-2 flex items-center gap-2 text-caption text-muted">
          <span>
            {resultCount} of {totalCount} workflow{totalCount === 1 ? '' : 's'}
          </span>
          {hasFilters && (
            <Button variant="link" size="xs" onClick={onClear}>
              Clear
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}
