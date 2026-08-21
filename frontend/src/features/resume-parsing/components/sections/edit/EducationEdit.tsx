import type { Education } from '../../../types/parsedProfile';

import { removeAt, updateAt } from './arrayHelpers';
import { Field } from './EditFields';
import styles from './RepeatableEdit.module.css';

type EducationEditProps = {
  entries: Education[];
  onChange: (entries: Education[]) => void;
};

export function EducationEdit({ entries, onChange }: EducationEditProps) {
  const addEntry = () =>
    onChange([
      ...entries,
      { degree: null, field: null, institution: null, start_year: null, end_year: null },
    ]);

  return (
    <div className={styles.repeatable}>
      {entries.map((entry, index) => (
        <EducationEntryFields
          key={index}
          entry={entry}
          onChange={(patch) => onChange(updateAt(entries, index, patch))}
          onRemove={() => onChange(removeAt(entries, index))}
        />
      ))}
      <button type="button" className={styles.addEntryBtn} onClick={addEntry}>
        + Add education
      </button>
    </div>
  );
}

type EntryFieldsProps = {
  entry: Education;
  onChange: (patch: Partial<Education>) => void;
  onRemove: () => void;
};

function EducationEntryFields({ entry, onChange, onRemove }: EntryFieldsProps) {
  return (
    <div className={styles.entryEdit}>
      <div className={styles.grid2}>
        <Field
          label="Degree"
          value={entry.degree ?? ''}
          onChange={(v) => onChange({ degree: v || null })}
        />
        <Field
          label="Field of study"
          value={entry.field ?? ''}
          onChange={(v) => onChange({ field: v || null })}
        />
      </div>
      <Field
        label="Institution"
        value={entry.institution ?? ''}
        onChange={(v) => onChange({ institution: v || null })}
      />
      <div className={styles.grid2}>
        <Field
          label="Start year"
          value={entry.start_year ?? ''}
          placeholder="2019"
          onChange={(v) => onChange({ start_year: v || null })}
        />
        <Field
          label="End year"
          value={entry.end_year ?? ''}
          placeholder="2023"
          onChange={(v) => onChange({ end_year: v || null })}
        />
      </div>
      <button type="button" className={styles.removeBtn} onClick={onRemove}>
        Remove
      </button>
    </div>
  );
}
