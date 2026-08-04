import { SectionShell } from '@shared/ui';
import { formatRange, joinPresent } from '@shared/utils/format';

import type { Education } from '../../types/parsedProfile';

import { EntryCard } from './EntryCard';

type EducationSectionProps = {
  education: Education[];
};

export function EducationSection({ education }: EducationSectionProps) {
  return (
    <SectionShell
      title="Education"
      count={education.length}
      emptyLabel="No education history on this resume"
      isEmpty={education.length === 0}
    >
      {education.map((entry, index) => (
        <EntryCard
          key={`${entry.degree ?? 'degree'}-${entry.institution ?? ''}-${index}`}
          heading={joinPresent([entry.degree, entry.field], ', ')}
          subheading={entry.institution}
          meta={[formatRange(entry.start_year, entry.end_year)]}
        />
      ))}
    </SectionShell>
  );
}
