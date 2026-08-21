import { useCallback, useState } from 'react';

import styles from './EditFields.module.css';

type FieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
};

export function Field({ label, value, onChange, placeholder, disabled }: FieldProps) {
  return (
    <label className={styles.field}>
      <span className={styles.fieldLabel}>{label}</span>
      <input
        type="text"
        className={styles.input}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

type TextAreaFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
};

export function TextAreaField({ label, value, onChange }: TextAreaFieldProps) {
  return (
    <label className={styles.field}>
      <span className={styles.fieldLabel}>{label}</span>
      <textarea
        className={styles.textarea}
        rows={3}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

type TagEditorProps = {
  items: string[];
  onChange: (items: string[]) => void;
  placeholder: string;
  ariaLabel: string;
};

/** Add-a-chip editor for every string[] field: skills, job titles, links, technologies. */
export function TagEditor({ items, onChange, placeholder, ariaLabel }: TagEditorProps) {
  const [draft, setDraft] = useState('');

  const commit = useCallback(() => {
    const value = draft.trim();
    if (value && !items.includes(value)) onChange([...items, value]);
    setDraft('');
  }, [draft, items, onChange]);

  const remove = useCallback(
    (item: string) => onChange(items.filter((existing) => existing !== item)),
    [items, onChange],
  );

  return (
    <div>
      {items.length > 0 && (
        <ul className={styles.tagList} aria-label={ariaLabel}>
          {items.map((item) => (
            <li key={item} className={styles.tag}>
              {item}
              <button
                type="button"
                className={styles.tagRemove}
                onClick={() => remove(item)}
                aria-label={`Remove ${item}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className={styles.tagAddRow}>
        <input
          type="text"
          className={styles.input}
          value={draft}
          placeholder={placeholder}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            // Enter adds a tag instead of submitting the (nonexistent) form.
            if (event.key === 'Enter') {
              event.preventDefault();
              commit();
            }
          }}
        />
        <button type="button" className={styles.addBtn} onClick={commit} disabled={!draft.trim()}>
          Add
        </button>
      </div>
    </div>
  );
}
