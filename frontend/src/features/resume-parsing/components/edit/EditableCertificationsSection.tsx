import type { Certification } from '../../types/parsedProfile';

import { EditableField } from './EditableField';
import { EditableRepeatingSection } from './EditableRepeatingSection';

type EditableCertificationsSectionProps = {
  certifications: Certification[];
  onChange: (certifications: Certification[]) => void;
};

const emptyEntry = (): Certification => ({
  name: '',
  issuer: '',
  year: '',
});

export function EditableCertificationsSection({
  certifications,
  onChange,
}: EditableCertificationsSectionProps) {
  return (
    <EditableRepeatingSection
      title="Certifications"
      items={certifications}
      onChange={onChange}
      emptyEntry={emptyEntry}
      addLabel="Add certification"
      renderEntry={(entry, update) => (
        <>
          <EditableField label="Name" value={entry.name ?? ''} onChange={(v) => update({ name: v })} />
          <EditableField label="Issuer" value={entry.issuer ?? ''} onChange={(v) => update({ issuer: v })} />
          <EditableField label="Year" value={entry.year ?? ''} onChange={(v) => update({ year: v })} />
        </>
      )}
    />
  );
}
