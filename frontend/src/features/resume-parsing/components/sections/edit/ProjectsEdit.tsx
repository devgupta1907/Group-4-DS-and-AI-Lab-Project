import type { Project } from '../../../types/parsedProfile';

import { removeAt, updateAt } from './arrayHelpers';
import { Field, TagEditor, TextAreaField } from './EditFields';
import styles from './RepeatableEdit.module.css';

type ProjectsEditProps = {
  entries: Project[];
  onChange: (entries: Project[]) => void;
};

export function ProjectsEdit({ entries, onChange }: ProjectsEditProps) {
  const addEntry = () =>
    onChange([...entries, { name: null, description: null, technologies: [] }]);

  return (
    <div className={styles.repeatable}>
      {entries.map((entry, index) => (
        <ProjectEntryFields
          key={index}
          entry={entry}
          index={index}
          onChange={(patch) => onChange(updateAt(entries, index, patch))}
          onRemove={() => onChange(removeAt(entries, index))}
        />
      ))}
      <button type="button" className={styles.addEntryBtn} onClick={addEntry}>
        + Add project
      </button>
    </div>
  );
}

type EntryFieldsProps = {
  entry: Project;
  index: number;
  onChange: (patch: Partial<Project>) => void;
  onRemove: () => void;
};

function ProjectEntryFields({ entry, index, onChange, onRemove }: EntryFieldsProps) {
  return (
    <div className={styles.entryEdit}>
      <Field
        label="Name"
        value={entry.name ?? ''}
        onChange={(v) => onChange({ name: v || null })}
      />
      <TextAreaField
        label="Description"
        value={entry.description ?? ''}
        onChange={(v) => onChange({ description: v || null })}
      />
      <TagEditor
        items={entry.technologies}
        onChange={(technologies) => onChange({ technologies })}
        placeholder="Add a technology"
        ariaLabel={`Technologies for ${entry.name ?? `project ${index + 1}`}`}
      />
      <button type="button" className={styles.removeBtn} onClick={onRemove}>
        Remove
      </button>
    </div>
  );
}
