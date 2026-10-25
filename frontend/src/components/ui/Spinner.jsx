import { Loader2 } from 'lucide-react';

/**
 * Spinner — the ONLY spinner. Use it inline, inside a sentence or a button
 * ("Saving…"). Page and section loads use <LoadingState> (skeletons) instead:
 * a spinner says "wait", a skeleton says what is coming and lands with no
 * layout shift.
 */
export default function Spinner({ className = 'h-4 w-4', label = 'Loading' }) {
  return (
    <span role="status" aria-label={label} className="inline-flex shrink-0">
      <Loader2 aria-hidden="true" className={`animate-spin ${className}`} />
    </span>
  );
}
