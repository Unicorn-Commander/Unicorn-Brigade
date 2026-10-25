import { useId, useState } from 'react';
import { Plus, X } from 'lucide-react';
import { Button, Chip, Input } from './ui';

/**
 * TagInput — a list of short strings (stop sequences, labels) with an input to
 * add more. Enter adds, Backspace on an empty input removes the last tag, each
 * tag has its own named remove control.
 *
 *   <TagInput tags={stop} onAdd={…} onRemove={…} placeholder="END" maxTags={10} />
 */
export default function TagInput({
  tags = [],
  onAdd,
  onRemove,
  placeholder = 'Add a tag…',
  maxTags = 10,
  disabled = false,
  label = 'Add a tag',
  id: idProp,
}) {
  const auto = useId();
  const id = idProp || auto;
  const [draft, setDraft] = useState('');
  const full = tags.length >= maxTags;

  const add = () => {
    const tag = draft.trim();
    if (!tag || tags.includes(tag) || full) return;
    onAdd?.(tag);
    setDraft('');
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      add();
    } else if (e.key === 'Backspace' && !draft && tags.length && !disabled) {
      onRemove?.(tags[tags.length - 1]);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      {tags.length > 0 ? (
        <ul className="flex flex-wrap gap-1.5" aria-label="Tags">
          {tags.map((tag) => (
            <li key={tag} className="inline-flex">
              <Chip tone="accent" size="md" className="font-mono">
                {tag}
                {!disabled && (
                  <button
                    type="button"
                    onClick={() => onRemove?.(tag)}
                    aria-label={`Remove ${tag}`}
                    className="-mr-1 ml-0.5 flex h-5 w-5 items-center justify-center rounded-full transition-colors duration-fast hover:bg-accent/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <X aria-hidden="true" className="h-3 w-3" />
                  </button>
                )}
              </Chip>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-caption text-muted">None yet.</p>
      )}

      {!disabled && !full && (
        <div className="flex items-center gap-2">
          <Input
            id={id}
            size="sm"
            aria-label={label}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={placeholder}
            maxLength={50}
          />
          <Button type="button" variant="secondary" size="sm" icon={Plus} onClick={add} disabled={!draft.trim()}>
            Add
          </Button>
        </div>
      )}
      {full && !disabled && <p className="text-caption text-warn">Maximum of {maxTags} reached.</p>}
    </div>
  );
}
