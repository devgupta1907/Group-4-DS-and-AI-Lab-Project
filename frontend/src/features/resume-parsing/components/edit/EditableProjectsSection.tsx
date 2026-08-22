import type { Project } from '../../types/parsedProfile';

import { EditableField } from './EditableField';
import { EditableRepeatingSection } from './EditableRepeatingSection';
import { EditableTagList } from './EditableTagList';
import styles from './EditableRepeatingSection.module.css';

type EditableProjectsSectionProps = {
  projects: Project[];
  onChange: (projects: Project[]) => void;
};

const emptyEntry = (): Project => ({
  name: '',
  description: '',
  technologies: [],
});

export function EditableProjectsSection({ projects, onChange }: EditableProjectsSectionProps) {
  return (
    <EditableRepeatingSection
      title="Projects"
      items={projects}
      onChange={onChange}
      emptyEntry={emptyEntry}
      addLabel="Add project"
      renderEntry={(entry, update) => (
        <>
          <EditableField label="Name" value={entry.name ?? ''} onChange={(v) => update({ name: v })} />
          <div className={styles.fullWidth}>
            <EditableField
              label="Description"
              value={entry.description ?? ''}
              onChange={(v) => update({ description: v })}
              multiline
            />
          </div>
          <div className={styles.fullWidth}>
            <EditableTagList
              label="Technologies"
              items={entry.technologies}
              onChange={(technologies) => update({ technologies })}
              placeholder="e.g. React"
            />
          </div>
        </>
      )}
    />
  );
}
