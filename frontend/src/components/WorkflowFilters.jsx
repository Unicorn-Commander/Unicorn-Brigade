/**
 * WorkflowFilters - Advanced filtering controls for workflows
 *
 * Features:
 * - Search bar
 * - Domain filter
 * - Complexity filter
 * - Tag filter
 * - Sort options
 * - View mode toggle (grid/list)
 */

import {
  Search,
  Filter,
  X,
  Grid3x3,
  List,
  ArrowUpDown,
  Tag,
  TrendingUp,
  Sparkles,
} from 'lucide-react';

const WorkflowFilters = ({
  searchQuery,
  setSearchQuery,
  selectedTag,
  setSelectedTag,
  selectedComplexity,
  setSelectedComplexity,
  viewMode,
  setViewMode,
  sortBy,
  setSortBy,
  allTags,
  resultCount,
  totalCount,
}) => {
  const hasActiveFilters = searchQuery || selectedTag || selectedComplexity;

  const clearFilters = () => {
    setSearchQuery('');
    setSelectedTag('');
    setSelectedComplexity('');
  };

  return (
    <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6 space-y-4">
      {/* Top Row: Search + View Toggle */}
      <div className="flex gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search workflows by name, description, or tags..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-10 py-2.5 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-slate-200 placeholder:text-slate-500"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 transform -translate-y-1/2 text-slate-400 hover:text-slate-200 transition-colors"
              title="Clear search"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center bg-slate-800/50 rounded-lg p-1 border border-slate-700">
          <button
            onClick={() => setViewMode('grid')}
            className={`p-2 rounded transition-colors ${
              viewMode === 'grid'
                ? 'bg-purple-500 text-white'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Grid View"
          >
            <Grid3x3 className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={`p-2 rounded transition-colors ${
              viewMode === 'list'
                ? 'bg-purple-500 text-white'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="List View"
          >
            <List className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Bottom Row: Filters + Sort */}
      <div className="flex flex-wrap gap-3">
        {/* Tag Filter */}
        <div className="flex-1 min-w-[200px]">
          <div className="relative">
            <Tag className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
            <select
              value={selectedTag}
              onChange={(e) => setSelectedTag(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-slate-200 appearance-none cursor-pointer"
            >
              <option value="">All Tags</option>
              <optgroup label="Domains">
                {allTags.filter(tag =>
                  ['research', 'finance', 'content', 'sales', 'devops', 'legal', 'medical', 'investigation'].includes(tag)
                ).map(tag => (
                  <option key={tag} value={tag}>{tag}</option>
                ))}
              </optgroup>
              <optgroup label="Other Tags">
                {allTags.filter(tag =>
                  !['research', 'finance', 'content', 'sales', 'devops', 'legal', 'medical', 'investigation'].includes(tag)
                ).map(tag => (
                  <option key={tag} value={tag}>{tag}</option>
                ))}
              </optgroup>
            </select>
          </div>
        </div>

        {/* Complexity Filter */}
        <div className="flex-1 min-w-[180px]">
          <div className="relative">
            <TrendingUp className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
            <select
              value={selectedComplexity}
              onChange={(e) => setSelectedComplexity(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-slate-200 appearance-none cursor-pointer"
            >
              <option value="">All Complexity</option>
              <option value="simple">Simple (≤3 steps)</option>
              <option value="moderate">Moderate (4-5 steps)</option>
              <option value="complex">Complex (6+ steps)</option>
            </select>
          </div>
        </div>

        {/* Sort */}
        <div className="flex-1 min-w-[180px]">
          <div className="relative">
            <ArrowUpDown className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-slate-200 appearance-none cursor-pointer"
            >
              <option value="newest">Newest First</option>
              <option value="name-asc">Name (A-Z)</option>
              <option value="name-desc">Name (Z-A)</option>
              <option value="steps-asc">Fewest Steps</option>
              <option value="steps-desc">Most Steps</option>
              <option value="cost-asc">Lowest Cost</option>
              <option value="cost-desc">Highest Cost</option>
            </select>
          </div>
        </div>

        {/* Clear Filters Button */}
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="px-4 py-2 bg-slate-800/50 hover:bg-slate-700/50 border border-slate-700 rounded-lg transition-colors flex items-center gap-2 text-slate-300"
          >
            <X className="w-4 h-4" />
            <span className="text-sm">Clear</span>
          </button>
        )}
      </div>

      {/* Results Count */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-700/50">
        <div className="flex items-center gap-2 text-sm">
          <Sparkles className="w-4 h-4 text-purple-400" />
          <span className="text-slate-400">
            Showing <span className="font-medium text-white">{resultCount}</span> of{' '}
            <span className="font-medium text-white">{totalCount}</span> workflows
          </span>
        </div>

        {hasActiveFilters && (
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-purple-400" />
            <span className="text-sm text-purple-400 font-medium">Filters Active</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default WorkflowFilters;
