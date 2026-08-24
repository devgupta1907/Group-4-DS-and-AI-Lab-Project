import type { Certification } from '../../../types/parsedProfile';

import { removeAt, updateAt } from './arrayHelpers';
import { Field } from './EditFields';
import styles from './RepeatableEdit.module.css';

type CertificationsEditProps = {
  entries: Certification[];
  onChange: (entries: Certification[]) => void;
};

export function CertificationsEdit({ entries, onChange }: CertificationsEditProps) {
  const addEntry = () => onChange([...entries, { name: null, issuer: null, year: null }]);

  return (
    <div className={styles.repeatable}>
      {entries.map((entry, index) => (
        <CertificationEntryFields
          key={index}
          entry={entry}
          onChange={(patch) => onChange(updateAt(entries, index, patch))}
          onRemove={() => onChange(removeAt(entries, index))}
        />
      ))}
      <button type="button" className={styles.addEntryBtn} onClick={addEntry}>
        + Add certification
      </button>
    </div>
  );
}

type EntryFieldsProps = {
  entry: Certification;
  onChange: (patch: Partial<Certification>) => void;
  onRemove: () => void;
};

function CertificationEntryFields({ entry, onChange, onRemove }: EntryFieldsProps) {
  return (
    <div className={styles.entryEdit}>
      <div className={styles.grid2}>
        <Field
          label="Name"
          value={entry.name ?? ''}
          onChange={(v) => onChange({ name: v || null })}
        />
        <Field
          label="Issuer"
          value={entry.issuer ?? ''}
          onChange={(v) => onChange({ issuer: v || null })}
        />
      </div>
      <Field
        label="Year"
        value={entry.year ?? ''}
        placeholder="2022"
        onChange={(v) => onChange({ year: v || null })}
      />
      <button type="button" className={styles.removeBtn} onClick={onRemove}>
        Remove
      </button>
    </div>
  );
}
