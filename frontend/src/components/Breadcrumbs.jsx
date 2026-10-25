import { Link, useLocation } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';
import { IconButton } from './ui';
import { pageFor } from './Navigation';

const SEGMENT_NAMES = { agent: 'Agent' };

/**
 * Breadcrumbs — a home IconButton, then one crumb per path segment. Names come
 * from the navigation's page list, so a renamed page renames its crumb.
 * Usually passed to <PageHeader breadcrumbs={<Breadcrumbs />}>.
 */
export default function Breadcrumbs({ className = '' }) {
  const { pathname } = useLocation();
  const segments = pathname.split('/').filter(Boolean);
  if (segments.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className={`text-body-sm ${className}`}>
      <ol className="flex flex-wrap items-center gap-1">
        <li className="flex">
          <IconButton as={Link} to="/dashboard" icon={Home} label="Dashboard" size="xs" />
        </li>
        {segments.map((segment, index) => {
          const routeTo = `/${segments.slice(0, index + 1).join('/')}`;
          const isLast = index === segments.length - 1;
          const name = pageFor(routeTo)?.path === routeTo ? pageFor(routeTo).label : SEGMENT_NAMES[segment] || segment;
          return (
            <li key={routeTo} className="flex items-center gap-1">
              <ChevronRight aria-hidden="true" className="h-3.5 w-3.5 text-subtle" />
              {isLast ? (
                <span aria-current="page" className="truncate font-medium text-fg">
                  {name}
                </span>
              ) : (
                <Link to={routeTo} className="rounded-chip px-1 text-muted transition-colors duration-fast hover:text-fg">
                  {name}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
