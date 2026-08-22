import type { ReactNode } from 'react';

import { Button } from '@shared/ui';

import styles from './EditableRepeatingSection.module.css';

type EditableRepeatingSectionProps<T> = {
  title: string;
  items: T[];
  onChange: (items: T[]) => void;
  emptyEntry: () => T;
  renderEntry: (entry: T, update: (patch: Partial<T>) => void) => ReactNode;
  addLabel: string;
};

/**
 * Shared shape for Experience/Education/Projects/Certifications in edit
 * mode: a stack of cards, each with its own fields plus a Remove button,
 * and an Add button at the bottom that appends `emptyEntry()`.
 *
 * `renderEntry` gets a `update(patch)` callback that merges a partial
 * object into that one entry — so a caller writes
 * `update({ job_title: value })` instead of re-deriving the whole array
 * index/splice dance per field.
 */
export function EditableRepeatingSection<T>({
  title,
  items,
  onChange,
  emptyEntry,
  renderEntry,
  addLabel,
}: EditableRepeatingSectionProps<T>) {
  const updateAt = (index: number, patch: Partial<T>) => {
    onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  };

  const removeAt = (index: number) => {
    onChange(items.filter((_, i) => i !== index));
  };

  const add = () => {
    onChange([...items, emptyEntry()]);
  };

  return (
    <div className={styles.wrap}>
      <span className={styles.title}>{title}</span>
      {items.length === 0 && <p className={styles.empty}>Nothing here yet.</p>}
      {items.map((item, index) => (
        <div className={styles.card} key={index}>
          <div className={styles.fields}>{renderEntry(item, (patch) => updateAt(index, patch))}</div>
          <Button variant="ghost" size="sm" onClick={() => removeAt(index)}>
            Remove
          </Button>
        </div>
      ))}
      <Button variant="secondary" size="sm" onClick={add}>
        {addLabel}
      </Button>
    </div>
  );
}
