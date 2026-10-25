/**
 * PageHeader + Page — the one page frame.
 *
 *   <Page>
 *     <PageHeader
 *       eyebrow="Agents"                       // small uppercase section word
 *       title="Agent Library"                  // plain, strong — never a gradient
 *       description="57 agents across 20 domains"
 *       actions={<Button icon={Plus}>Build an agent</Button>}
 *       tabs={<Tabs … />}                      // optional strip under the header
 *     />
 *     …content…
 *   </Page>
 *
 * Geometry is owned here: 16px gutters on phones, 24px from `sm`, consistent
 * vertical rhythm, actions wrap under the title on narrow screens.
 */
export function Page({ children, className = '', width = 'full' }) {
  const max = { full: '', wide: 'max-w-7xl', narrow: 'max-w-3xl' }[width] || '';
  return <div className={`mx-auto w-full px-4 pb-10 pt-4 sm:px-6 sm:pt-6 ${max} ${className}`}>{children}</div>;
}

export default function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  icon: Icon,
  tabs,
  breadcrumbs,
  className = '',
}) {
  return (
    <header className={`mb-5 ${className}`}>
      {breadcrumbs && <div className="mb-3">{breadcrumbs}</div>}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          {Icon && (
            <span
              aria-hidden="true"
              className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-control border border-border bg-elevated/70 text-accent"
            >
              <Icon className="h-5 w-5" />
            </span>
          )}
          <div className="min-w-0">
            {eyebrow && <p className="mb-1 text-micro font-semibold uppercase tracking-wider text-muted">{eyebrow}</p>}
            <h1 className="text-title text-fg-strong">{title}</h1>
            {description && <p className="mt-1 max-w-2xl text-body text-muted">{description}</p>}
          </div>
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">{actions}</div>}
      </div>
      {tabs && <div className="mt-4">{tabs}</div>}
    </header>
  );
}

/** A section heading inside a page: smaller, same rhythm. */
export function SectionHeader({ title, description, actions, className = '' }) {
  return (
    <div className={`mb-3 flex flex-wrap items-end justify-between gap-2 ${className}`}>
      <div>
        <h2 className="text-heading text-fg-strong">{title}</h2>
        {description && <p className="mt-0.5 text-body-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
