import type { CandidateProfile } from '../../types/parsedProfile';

import { EditableCertificationsSection } from './EditableCertificationsSection';
import { EditableContactSection } from './EditableContactSection';
import { EditableEducationSection } from './EditableEducationSection';
import { EditableExperienceSection } from './EditableExperienceSection';
import { EditableProjectsSection } from './EditableProjectsSection';
import styles from './EditableProfileView.module.css';
import { EditableTagList } from './EditableTagList';

type EditableProfileViewProps = {
  draft: CandidateProfile;
  onChange: (updater: (draft: CandidateProfile) => CandidateProfile) => void;
};

/**
 * The edit-mode counterpart to `ProfileView` — same section order (Contact,
 * Skills, Experience, Education, Projects, Certifications, Job titles), each
 * swapped for its editable equivalent. `onChange` is `useProfileEditor`'s
 * `updateDraft`: every section calls it with a small updater that only
 * touches its own slice of the profile.
 */
export function EditableProfileView({ draft, onChange }: EditableProfileViewProps) {
  return (
    <div className={styles.view}>
      <section className={styles.section}>
        <h3 className={styles.title}>Contact</h3>
        <EditableContactSection
          contact={draft.contact}
          onChange={(contact) => onChange((prev) => ({ ...prev, contact }))}
        />
      </section>

      <section className={styles.section}>
        <EditableTagList
          label="Skills"
          items={draft.skills}
          onChange={(skills) => onChange((prev) => ({ ...prev, skills }))}
          placeholder="e.g. Python"
        />
      </section>

      <section className={styles.section}>
        <EditableExperienceSection
          experience={draft.experience}
          onChange={(experience) => onChange((prev) => ({ ...prev, experience }))}
        />
      </section>

      <section className={styles.section}>
        <EditableEducationSection
          education={draft.education}
          onChange={(education) => onChange((prev) => ({ ...prev, education }))}
        />
      </section>

      <section className={styles.section}>
        <EditableProjectsSection
          projects={draft.projects}
          onChange={(projects) => onChange((prev) => ({ ...prev, projects }))}
        />
      </section>

      <section className={styles.section}>
        <EditableCertificationsSection
          certifications={draft.certifications}
          onChange={(certifications) => onChange((prev) => ({ ...prev, certifications }))}
        />
      </section>

      <section className={styles.section}>
        <EditableTagList
          label="Job titles"
          items={draft.job_titles}
          onChange={(job_titles) => onChange((prev) => ({ ...prev, job_titles }))}
          placeholder="e.g. Data Analyst"
        />
      </section>
    </div>
  );
}
