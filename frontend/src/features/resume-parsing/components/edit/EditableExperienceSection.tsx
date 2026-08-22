import type { Experience } from '../../types/parsedProfile';

import { EditableField } from './EditableField';
import { EditableRepeatingSection } from './EditableRepeatingSection';
import styles from './EditableRepeatingSection.module.css';

type EditableExperienceSectionProps = {
  experience: Experience[];
  onChange: (experience: Experience[]) => void;
};

const emptyEntry = (): Experience => ({
  job_title: '',
  company: '',
  location: '',
  start_date: '',
  end_date: '',
  current_role: false,
  description: '',
});

export function EditableExperienceSection({ experience, onChange }: EditableExperienceSectionProps) {
  return (
    <EditableRepeatingSection
      title="Experience"
      items={experience}
      onChange={onChange}
      emptyEntry={emptyEntry}
      addLabel="Add role"
      renderEntry={(entry, update) => (
        <>
          <EditableField label="Job title" value={entry.job_title ?? ''} onChange={(v) => update({ job_title: v })} />
          <EditableField label="Company" value={entry.company ?? ''} onChange={(v) => update({ company: v })} />
          <EditableField label="Location" value={entry.location ?? ''} onChange={(v) => update({ location: v })} />
          <EditableField
            label="Start date"
            value={entry.start_date ?? ''}
            onChange={(v) => update({ start_date: v })}
            placeholder="e.g. 2022-03"
          />
          <EditableField
            label="End date"
            value={entry.end_date ?? ''}
            onChange={(v) => update({ end_date: v })}
            placeholder="e.g. 2024-06 or Present"
          />
          <label className={styles.checkboxField}>
            <input
              type="checkbox"
              checked={entry.current_role ?? false}
              onChange={(event) => update({ current_role: event.target.checked })}
            />
            Current role
          </label>
          <div className={styles.fullWidth}>
            <EditableField
              label="Description"
              value={entry.description ?? ''}
              onChange={(v) => update({ description: v })}
              multiline
            />
          </div>
        </>
      )}
    />
  );
}
