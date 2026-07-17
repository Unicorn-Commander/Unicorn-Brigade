/**
 * Button primitive — consistent variants/sizes over the ~274 ad-hoc inline
 * buttons in the app. Renders a real <button> (keyboard + focus-visible ring
 * come from the global focus styles). Adopt incrementally.
 */
const VARIANTS = {
  primary:
    'bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white hover:from-unicorn-500 hover:to-unicorn-400 shadow-lg hover:shadow-unicorn-500/25',
  secondary:
    'bg-slate-800/60 text-slate-200 border border-border/60 hover:bg-slate-700/60',
  ghost: 'text-muted hover:text-white hover:bg-white/5',
  danger: 'bg-red-600 text-white hover:bg-red-700',
};

const SIZES = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
};

export default function Button({
  as: Comp = 'button',
  variant = 'primary',
  size = 'md',
  className = '',
  type = 'button',
  children,
  ...props
}) {
  const isButton = Comp === 'button';
  return (
    <Comp
      type={isButton ? type : undefined}
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed ${
        VARIANTS[variant] || VARIANTS.primary
      } ${SIZES[size] || SIZES.md} ${className}`}
      {...props}
    >
      {children}
    </Comp>
  );
}
