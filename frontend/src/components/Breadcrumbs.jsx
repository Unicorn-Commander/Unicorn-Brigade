import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';

const ROUTE_NAMES = {
  '': 'Dashboard',
  dashboard: 'Dashboard',
  chat: 'Chat',
  conversations: 'Conversations',
  orchestration: 'Orchestration',
  workflows: 'Workflows',
  'ralph-monitor': 'Ralph Monitor',
  knowledge: 'Knowledge Graph',
  library: 'Agent Library',
  tools: 'Tool Library',
  'mcp-servers': 'MCP Servers',
  'mcp-docs': 'MCP Documentation',
  langflow: 'Langflow Flows',
  docs: 'API Documentation',
  'code-attribution': 'Code Attribution',
  monitoring: 'Monitoring',
  'scheduled-runs': 'Scheduled Runs',
  organization: 'Organization',
  settings: 'Settings',
};

export default function Breadcrumbs() {
  const location = useLocation();
  const pathnames = location.pathname.split('/').filter((x) => x);

  if (pathnames.length === 0) {
    return null;
  }

  return (
    <nav aria-label="Breadcrumb" className="flex items-center space-x-2 text-sm mb-6">
      <Link
        to="/dashboard"
        aria-label="Home"
        className="flex items-center text-muted hover:text-fg transition-colors"
      >
        <Home className="w-4 h-4" aria-hidden="true" />
      </Link>

      {pathnames.map((pathname, index) => {
        const routeTo = `/${pathnames.slice(0, index + 1).join('/')}`;
        const isLast = index === pathnames.length - 1;
        const name = ROUTE_NAMES[pathname] || pathname;

        return (
          <React.Fragment key={routeTo}>
            <ChevronRight className="w-4 h-4 text-muted" />
            {isLast ? (
              <span className="text-fg font-medium">{name}</span>
            ) : (
              <Link
                to={routeTo}
                className="text-muted hover:text-fg transition-colors"
              >
                {name}
              </Link>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}
