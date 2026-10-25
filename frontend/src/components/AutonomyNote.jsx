/**
 * The fleet audit's note on an autonomous job, shown under its
 * responsibility: muted, two lines until expanded. A note that opens with
 * BROKEN or FAILING (danger) or ORPHAN (warn) has that word tinted so the
 * finding reads at a glance — e.g. "BROKEN: script missing since the
 * 2026-04-30 git stash; recovered copy in scripts/recovered-20260825/."
 */
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { noteFlag } from '../utils/autonomy';
import { Button } from './ui';

const TONE = { danger: 'text-danger', warn: 'text-warn' };

export default function AutonomyNote({ notes, clamp = true, className = '' }) {
  const [open, setOpen] = useState(false);
  const [overflows, setOverflows] = useState(false);
  const ref = useRef(null);
  const id = useId();

  // Offer "Show all" only when the two-line clamp actually hides something.
  useLayoutEffect(() => {
    const measure = () => {
      const el = ref.current;
      if (el && clamp && !open) setOverflows(el.scrollHeight > el.clientHeight + 1);
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [notes, clamp, open]);
  useEffect(() => setOpen(false), [notes]);

  if (!notes) return null;
  const flag = noteFlag(notes);
  return (
    <div className={className}>
      <p id={id} ref={ref} className={`whitespace-pre-line text-body-sm text-muted ${clamp && !open ? 'line-clamp-2' : ''}`}>
        <span className="text-subtle">Note — </span>
        {flag ? (
          <>
            <span className={`font-semibold ${TONE[flag.tone] || ''}`}>{flag.word}</span>
            {flag.rest}
          </>
        ) : (
          notes
        )}
      </p>
      {clamp && (overflows || open) && (
        <Button variant="link" size="xs" aria-expanded={open} aria-controls={id} onClick={() => setOpen((v) => !v)}>
          {open ? 'Show less' : 'Show the whole note'}
        </Button>
      )}
    </div>
  );
}
