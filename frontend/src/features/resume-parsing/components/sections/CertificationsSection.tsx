import { SectionShell } from '@shared/ui';

import type { Certification } from '../../types/parsedProfile';

import { EntryCard } from './EntryCard';

type CertificationsSectionProps = {
  certifications: Certification[];
};

export function CertificationsSection({ certifications }: CertificationsSectionProps) {
  return (
    <SectionShell
      title="Certifications"
      count={certifications.length}
      emptyLabel="No certifications on this resume"
      isEmpty={certifications.length === 0}
    >
      {certifications.map((entry, index) => (
        <EntryCard
          key={`${entry.name ?? 'certification'}-${index}`}
          heading={entry.name}
          subheading={entry.issuer}
          meta={[entry.year]}
        />
      ))}
    </SectionShell>
  );
}
