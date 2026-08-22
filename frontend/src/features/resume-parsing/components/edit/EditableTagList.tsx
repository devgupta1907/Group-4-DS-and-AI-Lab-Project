import { useState, type KeyboardEvent } from 'react';

import styles from './EditableTagList.module.css';

type EditableTagListProps = {
  label: string;
  items: readonly string[];
  onChange: (items: string[]) => void;
  placeholder?: string;
};

/**
 * Add via Enter (or the button), remove via the × on each chip. Duplicate
 * and empty entries are silently ignored on add — the field never ends up
 * holding a blank tag or the same skill twice.
 */
export function EditableTagList({ label, items, onChange, placeholder }: EditableTagListProps) {
  const [draft, setDraft] = useState('');

  const commit = () => {
    const value = draft.trim();
    if (value && !items.includes(value)) {
      onChange([...items, value]);
    }
    setDraft('');
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      commit();
    }
  };

  const remove = (item: string) => {
    onChange(items.filter((existing) => existing !== item));
  };

  return (
    <div className={styles.wrap}>
      <span className={styles.label}>{label}</span>
      <ul className={styles.list}>
        {items.map((item) => (
          <li key={item} className={styles.tag}>
            {item}
            <button
              type="button"
              className={styles.remove}
              onClick={() => remove(item)}
              aria-label={`Remove ${item}`}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
      <div className={styles.addRow}>
        <input
          className={styles.input}
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder ?? 'Add and press Enter'}
        />
        <button type="button" className={styles.addButton} onClick={commit}>
          Add
        </button>
      </div>
    </div>
  );
}
