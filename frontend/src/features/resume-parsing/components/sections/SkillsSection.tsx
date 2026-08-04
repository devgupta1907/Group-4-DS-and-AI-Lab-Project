import { SectionShell, TagList } from '@shared/ui';

type SkillsSectionProps = {
  skills: string[];
};

export function SkillsSection({ skills }: SkillsSectionProps) {
  return (
    <SectionShell
      title="Skills"
      count={skills.length}
      emptyLabel="No skills listed on this resume"
      isEmpty={skills.length === 0}
    >
      <TagList items={skills} label="Extracted skills" />
    </SectionShell>
  );
}
