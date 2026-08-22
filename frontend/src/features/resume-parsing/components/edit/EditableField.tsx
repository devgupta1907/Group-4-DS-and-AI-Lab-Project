import type { ChangeEvent } from 'react';

import styles from './EditableField.module.css';

type EditableFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  multiline?: boolean;
};

/**
 * One labeled input, styled to sit where a `DefinitionList` row would in
 * read-only mode. `value`/`onChange` treat `null` in the underlying
 * `CandidateProfile` field as `''` — the section component converts back
 * to `null` on blur/save if the field is left empty, since the parsed
 * schema uses `null` for "not present," not `''`.
 */
export function EditableField({ label, value, onChange, placeholder, multiline }: EditableFieldProps) {
  const handleChange = (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    onChange(event.target.value);
  };

  return (
    <label className={styles.field}>
      <span className={styles.label}>{label}</span>
      {multiline ? (
        <textarea className={styles.textarea} value={value} onChange={handleChange} placeholder={placeholder} rows={3} />
      ) : (
        <input className={styles.input} type="text" value={value} onChange={handleChange} placeholder={placeholder} />
      )}
    </label>
  );
}
