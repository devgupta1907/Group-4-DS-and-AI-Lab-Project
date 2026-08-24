import type { Experience } from '../../../types/parsedProfile';

import { removeAt, updateAt } from './arrayHelpers';
import { Field, TextAreaField } from './EditFields';
import styles from './RepeatableEdit.module.css';

type ExperienceEditProps = {
  entries: Experience[];
  onChange: (entries: Experience[]) => void;
};

export function ExperienceEdit({ entries, onChange }: ExperienceEditProps) {
  const addEntry = () =>
    onChange([
      ...entries,
      {
        job_title: null,
        company: null,
        location: null,
        start_date: null,
        end_date: null,
        current_role: false,
        description: null,
      },
    ]);

  return (
    <div className={styles.repeatable}>
      {entries.map((entry, index) => (
        <ExperienceEntryFields
          key={index}
          entry={entry}
          onChange={(patch) => onChange(updateAt(entries, index, patch))}
          onRemove={() => onChange(removeAt(entries, index))}
        />
      ))}
      <button type="button" className={styles.addEntryBtn} onClick={addEntry}>
        + Add experience
      </button>
    </div>
  );
}

type EntryFieldsProps = {
  entry: Experience;
  onChange: (patch: Partial<Experience>) => void;
  onRemove: () => void;
};

function ExperienceEntryFields({ entry, onChange, onRemove }: EntryFieldsProps) {
  return (
    <div className={styles.entryEdit}>
      <div className={styles.grid2}>
        <Field
          label="Job title"
          value={entry.job_title ?? ''}
          onChange={(v) => onChange({ job_title: v || null })}
        />
        <Field
          label="Company"
          value={entry.company ?? ''}
          onChange={(v) => onChange({ company: v || null })}
        />
      </div>
      <Field
        label="Location"
        value={entry.location ?? ''}
        onChange={(v) => onChange({ location: v || null })}
      />
      <div className={styles.grid2}>
        <Field
          label="Start date"
          value={entry.start_date ?? ''}
          placeholder="Jan 2021"
          onChange={(v) => onChange({ start_date: v || null })}
        />
        <Field
          label="End date"
          value={entry.current_role ? '' : entry.end_date ?? ''}
          placeholder={entry.current_role ? 'Present' : 'Jan 2023'}
          disabled={entry.current_role === true}
          onChange={(v) => onChange({ end_date: v || null })}
        />
      </div>
      <label className={styles.checkboxRow}>
        <input
          type="checkbox"
          checked={entry.current_role === true}
          onChange={(event) =>
            onChange({
              current_role: event.target.checked,
              end_date: event.target.checked ? null : entry.end_date,
            })
          }
        />
        Current role
      </label>
      <TextAreaField
        label="Description"
        value={entry.description ?? ''}
        onChange={(v) => onChange({ description: v || null })}
      />
      <button type="button" className={styles.removeBtn} onClick={onRemove}>
        Remove
      </button>
    </div>
  );
}
