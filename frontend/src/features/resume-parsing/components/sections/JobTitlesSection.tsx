import { SectionShell, TagList } from '@shared/ui';

type JobTitlesSectionProps = {
  jobTitles: string[];
};

export function JobTitlesSection({ jobTitles }: JobTitlesSectionProps) {
  return (
    <SectionShell
      title="Job titles"
      count={jobTitles.length}
      emptyLabel="No role titles identified"
      isEmpty={jobTitles.length === 0}
    >
      <TagList items={jobTitles} label="Normalised role titles" />
    </SectionShell>
  );
}
