import { Badge, SectionShell } from '@shared/ui';
import { formatRange } from '@shared/utils/format';

import type { Experience } from '../../types/parsedProfile';

import { EntryCard } from './EntryCard';

type ExperienceSectionProps = {
  experience: Experience[];
};

export function ExperienceSection({ experience }: ExperienceSectionProps) {
  return (
    <SectionShell
      title="Experience"
      count={experience.length}
      emptyLabel="No work experience on this resume"
      isEmpty={experience.length === 0}
    >
      {experience.map((entry, index) => (
        <EntryCard
          key={`${entry.job_title ?? 'role'}-${entry.company ?? ''}-${index}`}
          heading={entry.job_title}
          subheading={entry.company}
          meta={[formatRange(entry.start_date, entry.end_date), entry.location]}
          badge={entry.current_role ? <Badge tone="success">Current</Badge> : null}
          body={entry.description}
        />
      ))}
    </SectionShell>
  );
}
