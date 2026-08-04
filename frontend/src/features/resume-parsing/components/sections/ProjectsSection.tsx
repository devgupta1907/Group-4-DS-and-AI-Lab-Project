import { SectionShell, TagList } from '@shared/ui';

import type { Project } from '../../types/parsedProfile';

import { EntryCard } from './EntryCard';

type ProjectsSectionProps = {
  projects: Project[];
};

export function ProjectsSection({ projects }: ProjectsSectionProps) {
  return (
    <SectionShell
      title="Projects"
      count={projects.length}
      // Only 5 of 86 gold-set resumes list projects, so empty is the norm here,
      // not a sign the parser missed something.
      emptyLabel="No projects on this resume"
      isEmpty={projects.length === 0}
    >
      {projects.map((project, index) => (
        <EntryCard
          key={`${project.name ?? 'project'}-${index}`}
          heading={project.name}
          body={project.description}
        >
          <TagList items={project.technologies} label="Technologies used" />
        </EntryCard>
      ))}
    </SectionShell>
  );
}
