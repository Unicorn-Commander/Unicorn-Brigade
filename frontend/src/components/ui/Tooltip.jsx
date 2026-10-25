import { cloneElement, isValidElement } from 'react';
import { Tooltip as ReactTooltip } from 'react-tooltip';

/**
 * Tooltip — one tooltip for the whole app.
 *
 * Wrap any element; the tooltip shows on hover AND keyboard focus (a `title`
 * attribute does neither reliably). One <TooltipHost> is mounted in App.jsx;
 * every <Tooltip> anchors to it through data attributes, so there is exactly
 * one tooltip element in the DOM, themed once in index.css (.ub-tooltip).
 *
 *   <Tooltip content="Open full chat"><IconButton … /></Tooltip>
 *
 * The tooltip is supplementary: the child still needs its own accessible name
 * (aria-label or text). Use `side` for placement: top (default) | bottom |
 * left | right.
 */
export const TOOLTIP_ID = 'ub-tooltip';

export default function Tooltip({ content, side = 'top', delay = 250, children }) {
  if (!content || !isValidElement(children)) return children ?? null;
  return cloneElement(children, {
    'data-tooltip-id': TOOLTIP_ID,
    'data-tooltip-content': typeof content === 'string' ? content : undefined,
    'data-tooltip-html': typeof content !== 'string' ? String(content) : undefined,
    'data-tooltip-place': side,
    'data-tooltip-delay-show': delay,
  });
}

/** Mount once, near the root. */
export function TooltipHost() {
  return (
    <ReactTooltip
      id={TOOLTIP_ID}
      className="ub-tooltip"
      classNameArrow="ub-tooltip-arrow"
      noArrow={false}
      opacity={1}
      offset={8}
      delayShow={250}
      positionStrategy="fixed"
      globalCloseEvents={{ escape: true, scroll: true }}
    />
  );
}
