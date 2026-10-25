/**
 * Card — the one panel.
 *
 *   variant   default (solid card) | glass (translucent, blurred) | elevated (nested tile)
 *   padding   none | sm | md (default) | lg
 *   interactive  hover lift + focus ring; pass `as="button"` or an onClick
 *
 *   <Card>
 *     <CardHeader title="Service health" description="Polled every 30s" actions={…} />
 *     <CardBody>…</CardBody>
 *     <CardFooter>…</CardFooter>
 *   </Card>
 */
const VARIANTS = {
  default: 'border border-border bg-card',
  glass: 'border border-border/70 bg-card/60 backdrop-blur-xl',
  elevated: 'border border-border bg-elevated/70',
};
const PAD = { none: '', sm: 'p-3', md: 'p-5', lg: 'p-6' };

export default function Card({
  as: Comp = 'div',
  variant = 'default',
  padding = 'md',
  interactive = false,
  className = '',
  children,
  ...props
}) {
  const clickable = interactive || typeof props.onClick === 'function';
  return (
    <Comp
      className={[
        'rounded-card text-left',
        VARIANTS[variant] || VARIANTS.default,
        PAD[padding] ?? PAD.md,
        clickable
          ? 'cursor-pointer transition-[border-color,box-shadow,transform] duration-base ease-standard hover:border-border-strong hover:shadow-e2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg'
          : '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      {...props}
    >
      {children}
    </Comp>
  );
}

export function CardHeader({ title, description, icon: Icon, actions, className = '' }) {
  return (
    <div className={`mb-4 flex items-start justify-between gap-3 ${className}`}>
      <div className="flex min-w-0 items-start gap-3">
        {Icon && (
          <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-elevated text-accent">
            <Icon className="h-4 w-4" />
          </span>
        )}
        <div className="min-w-0">
          <h3 className="text-lead font-semibold text-fg-strong">{title}</h3>
          {description && <p className="mt-0.5 text-body-sm text-muted">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
    </div>
  );
}

export function CardBody({ className = '', children }) {
  return <div className={className}>{children}</div>;
}

export function CardFooter({ className = '', children }) {
  return <div className={`mt-4 flex items-center justify-end gap-2 border-t border-border pt-3 ${className}`}>{children}</div>;
}
