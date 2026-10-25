import { forwardRef } from 'react';
import Button from './Button';
import Tooltip from './Tooltip';

/**
 * IconButton — a square, icon-only Button with a REQUIRED accessible name.
 * The `label` is both the aria-label and the tooltip, so an icon control is
 * never a mystery to a keyboard, a screen reader or a thumb.
 *
 *   <IconButton icon={X} label="Close" variant="ghost" size="sm" onClick={…} />
 */
const IconButton = forwardRef(function IconButton(
  { icon, label, variant = 'ghost', size = 'md', tooltip = true, ...props },
  ref
) {
  const btn = <Button ref={ref} iconOnly icon={icon} variant={variant} size={size} aria-label={label} {...props} />;
  return tooltip ? <Tooltip content={label}>{btn}</Tooltip> : btn;
});

export default IconButton;
