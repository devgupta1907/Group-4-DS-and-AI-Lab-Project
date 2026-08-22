import type { Education } from '../../types/parsedProfile';

import { EditableField } from './EditableField';
import { EditableRepeatingSection } from './EditableRepeatingSection';

type EditableEducationSectionProps = {
  education: Education[];
  onChange: (education: Education[]) => void;
};

const emptyEntry = (): Education => ({
  degree: '',
  field: '',
  institution: '',
  start_year: '',
  end_year: '',
});

export function EditableEducationSection({ education, onChange }: EditableEducationSectionProps) {
  return (
    <EditableRepeatingSection
      title="Education"
      items={education}
      onChange={onChange}
      emptyEntry={emptyEntry}
      addLabel="Add education"
      renderEntry={(entry, update) => (
        <>
          <EditableField label="Degree" value={entry.degree ?? ''} onChange={(v) => update({ degree: v })} />
          <EditableField label="Field" value={entry.field ?? ''} onChange={(v) => update({ field: v })} />
          <EditableField
            label="Institution"
            value={entry.institution ?? ''}
            onChange={(v) => update({ institution: v })}
          />
          <EditableField
            label="Start year"
            value={entry.start_year ?? ''}
            onChange={(v) => update({ start_year: v })}
          />
          <EditableField label="End year" value={entry.end_year ?? ''} onChange={(v) => update({ end_year: v })} />
        </>
      )}
    />
  );
}
