import { forwardRef, useId } from 'react';
import { ChevronDown } from 'lucide-react';

/**
 * Form primitives: <Field> wraps a control with a real <label>, optional help
 * and an error line that is announced (aria-describedby + role=alert).
 * <Input>, <Textarea> and <Select> share one geometry and one focus ring.
 *
 *   <Field label="Agent name" help="Shown on the org chart" error={errors.name}>
 *     <Input value={name} onChange={…} placeholder="Sgt. Scribe" />
 *   </Field>
 *
 * Sizes: sm (32px) · md (36px, default) · lg (44px — use on touch surfaces).
 */
const CONTROL =
  'w-full rounded-control border bg-surface/70 text-fg placeholder:text-subtle transition-[border-color,box-shadow] duration-fast ease-standard ' +
  'focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/35 ' +
  'disabled:cursor-not-allowed disabled:opacity-50 read-only:bg-elevated/50';
const EDGE = {
  normal: 'border-border-strong/70 hover:border-border-strong',
  invalid: 'border-danger/70 focus:border-danger focus:ring-danger/30',
};
const SIZES = { sm: 'h-8 px-2.5 text-body-sm', md: 'h-9 px-3 text-body', lg: 'h-11 px-3.5 text-lead' };

export const Input = forwardRef(function Input({ size = 'md', invalid, className = '', ...props }, ref) {
  return (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={`${CONTROL} ${invalid ? EDGE.invalid : EDGE.normal} ${SIZES[size] || SIZES.md} ${className}`}
      {...props}
    />
  );
});

export const Textarea = forwardRef(function Textarea({ invalid, rows = 3, className = '', ...props }, ref) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      aria-invalid={invalid || undefined}
      className={`${CONTROL} ${invalid ? EDGE.invalid : EDGE.normal} px-3 py-2 text-body leading-5 ${className}`}
      {...props}
    />
  );
});

export const Select = forwardRef(function Select({ size = 'md', invalid, className = '', children, ...props }, ref) {
  return (
    <span className="relative block">
      <select
        ref={ref}
        aria-invalid={invalid || undefined}
        className={`${CONTROL} ${invalid ? EDGE.invalid : EDGE.normal} ${SIZES[size] || SIZES.md} appearance-none pr-9 ${className}`}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
      />
    </span>
  );
});

export default function Field({ label, help, error, required, htmlFor, children, className = '', inline = false }) {
  const auto = useId();
  const id = htmlFor || auto;
  const helpId = help ? `${id}-help` : undefined;
  const errId = error ? `${id}-err` : undefined;
  const describedBy = [helpId, errId].filter(Boolean).join(' ') || undefined;
  // Clone the single control child with the ids so label/help/error are wired.
  const control =
    children && typeof children === 'object' && !Array.isArray(children)
      ? { ...children, props: { ...children.props, id: children.props.id || id, 'aria-describedby': describedBy, invalid: children.props.invalid ?? Boolean(error) } }
      : children;
  return (
    <div className={`${inline ? 'flex items-center gap-3' : 'flex flex-col gap-1.5'} ${className}`}>
      {label && (
        <label htmlFor={id} className="text-body-sm font-medium text-fg">
          {label}
          {required && (
            <span aria-hidden="true" className="ml-0.5 text-danger">
              *
            </span>
          )}
        </label>
      )}
      {control}
      {help && !error && (
        <p id={helpId} className="text-caption text-muted">
          {help}
        </p>
      )}
      {error && (
        <p id={errId} role="alert" className="text-caption text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
