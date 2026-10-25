import { forwardRef } from 'react';
import Spinner from './Spinner';

/**
 * Button — the one button.
 *
 *   variant  primary | secondary | ghost | outline | danger | link
 *   size     xs | sm | md | lg        (md = 36px, the default control height)
 *   loading  swaps the leading icon for a spinner and disables the control
 *   icon     a lucide component rendered before the label
 *   iconOnly square button; REQUIRES aria-label (prefer <IconButton>)
 *   touch    force a visible 44px box (e.g. the phone top bar)
 *
 * On a coarse pointer (a finger) every button below 44px gets an invisible
 * hit area that reaches 44×44 — the box you see stays compact, the box you
 * tap meets WCAG 2.5.5. Primitives own geometry, call sites own composition:
 * never pass px/py/text-* overrides in className, ask for a size instead.
 */
const VARIANTS = {
  primary:
    'bg-gradient-accent text-on-accent shadow-e1 hover:brightness-110 active:brightness-95 disabled:hover:brightness-100',
  secondary: 'bg-elevated text-fg border border-border hover:border-border-strong hover:bg-elevated/80',
  outline: 'bg-transparent text-fg border border-border-strong hover:bg-elevated/60',
  ghost: 'bg-transparent text-muted hover:text-fg hover:bg-elevated/70',
  danger: 'bg-danger-fill text-white hover:brightness-110 active:brightness-95',
  link: 'bg-transparent text-accent underline-offset-4 hover:underline',
};

// Labelled buttons: height, padding, type, gap, radius.
const SIZES = {
  xs: 'h-7 px-2 text-caption gap-1 rounded-chip',
  sm: 'h-8 px-2.5 text-body-sm gap-1.5 rounded-control',
  md: 'h-9 px-3.5 text-body gap-2 rounded-control',
  lg: 'h-11 px-5 text-lead gap-2 rounded-control',
};
// Icon-only buttons: a square with NO padding class at all. (Mixing p-0 with a
// size's px-N let the generated CSS order decide, and the padding won — the
// icon collapsed to a few pixels.)
const ICON_ONLY = {
  xs: 'h-7 w-7 rounded-chip',
  sm: 'h-8 w-8 rounded-control',
  md: 'h-9 w-9 rounded-control',
  lg: 'h-11 w-11 rounded-control',
};
// Link buttons size their text only.
const LINK_SIZES = { xs: 'text-caption gap-1', sm: 'text-body-sm gap-1.5', md: 'text-body gap-2', lg: 'text-lead gap-2' };

// Invisible 44px hit area on touch screens (pseudo-element; layout unchanged).
const TOUCH_HIT = {
  xs: "[@media(pointer:coarse)]:after:absolute [@media(pointer:coarse)]:after:-inset-2 [@media(pointer:coarse)]:after:content-['']",
  sm: "[@media(pointer:coarse)]:after:absolute [@media(pointer:coarse)]:after:-inset-1.5 [@media(pointer:coarse)]:after:content-['']",
  md: "[@media(pointer:coarse)]:after:absolute [@media(pointer:coarse)]:after:-inset-1 [@media(pointer:coarse)]:after:content-['']",
  lg: '',
};

const ICON_PX = { xs: 'h-3.5 w-3.5', sm: 'h-4 w-4', md: 'h-4 w-4', lg: 'h-5 w-5' };

const Button = forwardRef(function Button(
  {
    as: Comp = 'button',
    variant = 'primary',
    size = 'md',
    icon: Icon,
    iconRight: IconRight,
    iconOnly = false,
    loading = false,
    touch = false,
    type = 'button',
    className = '',
    disabled,
    children,
    ...props
  },
  ref
) {
  if (import.meta.env?.DEV && iconOnly && !props['aria-label']) {
    console.warn('<Button iconOnly> needs an aria-label.');
  }
  const isButton = Comp === 'button';
  const isDisabled = disabled || loading;
  const isLink = variant === 'link';
  const iconCls = `${ICON_PX[size] || ICON_PX.md} shrink-0`;
  const geometry = iconOnly
    ? ICON_ONLY[size] || ICON_ONLY.md
    : isLink
      ? LINK_SIZES[size] || LINK_SIZES.md
      : SIZES[size] || SIZES.md;
  return (
    <Comp
      ref={ref}
      type={isButton ? type : undefined}
      aria-disabled={!isButton && isDisabled ? true : undefined}
      disabled={isButton ? isDisabled : undefined}
      aria-busy={loading || undefined}
      className={[
        'relative inline-flex shrink-0 select-none items-center justify-center whitespace-nowrap font-medium',
        'transition-[background-color,border-color,color,filter,box-shadow] duration-fast ease-standard',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-surface',
        'disabled:cursor-not-allowed disabled:opacity-50',
        VARIANTS[variant] || VARIANTS.primary,
        geometry,
        touch ? 'min-h-touch min-w-touch' : TOUCH_HIT[size] || '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      {...props}
    >
      {loading ? <Spinner className={iconCls} /> : Icon ? <Icon aria-hidden="true" className={iconCls} /> : null}
      {!iconOnly && children}
      {!iconOnly && IconRight && !loading ? <IconRight aria-hidden="true" className={iconCls} /> : null}
    </Comp>
  );
});

export default Button;
