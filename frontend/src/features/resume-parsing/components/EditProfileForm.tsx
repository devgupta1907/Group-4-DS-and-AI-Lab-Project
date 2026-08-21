import { SectionShell } from '@shared/ui';

import type { ProfileEditor } from '../hooks/useProfileEditor';

import styles from './EditProfileForm.module.css';
import { CertificationsEdit } from './sections/edit/CertificationsEdit';
import { ContactEdit } from './sections/edit/ContactEdit';
import { TagEditor } from './sections/edit/EditFields';
import { EducationEdit } from './sections/edit/EducationEdit';
import { ExperienceEdit } from './sections/edit/ExperienceEdit';
import { ProjectsEdit } from './sections/edit/ProjectsEdit';

type EditProfileFormProps = {
  editor: ProfileEditor;
  error: string | null;
  submitting: boolean;
  onSave: () => void;
  onCancel: () => void;
};

/**
 * The editable counterpart to `ProfileView`.
 *
 * Same seven sections, same order, so switching between review and edit mode
 * reads as the same document rather than a different screen. Every field maps
 * 1:1 onto `CandidateProfile` — there is no separate "draft" shape on the
 * server, so what is saved here is exactly what the rest of the pipeline
 * reads on the next run.
 */
export function EditProfileForm({
  editor,
  error,
  submitting,
  onSave,
  onCancel,
}: EditProfileFormProps) {
  const { profile } = editor;

  return (
    <div className={styles.form}>
      <ContactEdit contact={profile.contact} onChange={editor.setContact} />

      <SectionShell title="Skills" count={profile.skills.length} emptyLabel="" isEmpty={false}>
        <TagEditor
          items={profile.skills}
          onChange={editor.setSkills}
          placeholder="Add a skill"
          ariaLabel="Skills"
        />
      </SectionShell>

      <SectionShell
        title="Experience"
        count={profile.experience.length}
        emptyLabel=""
        isEmpty={false}
      >
        <ExperienceEdit entries={profile.experience} onChange={editor.setExperience} />
      </SectionShell>

      <SectionShell
        title="Education"
        count={profile.education.length}
        emptyLabel=""
        isEmpty={false}
      >
        <EducationEdit entries={profile.education} onChange={editor.setEducation} />
      </SectionShell>

      <SectionShell title="Projects" count={profile.projects.length} emptyLabel="" isEmpty={false}>
        <ProjectsEdit entries={profile.projects} onChange={editor.setProjects} />
      </SectionShell>

      <SectionShell
        title="Certifications"
        count={profile.certifications.length}
        emptyLabel=""
        isEmpty={false}
      >
        <CertificationsEdit
          entries={profile.certifications}
          onChange={editor.setCertifications}
        />
      </SectionShell>

      <SectionShell
        title="Job titles"
        count={profile.job_titles.length}
        emptyLabel=""
        isEmpty={false}
      >
        <TagEditor
          items={profile.job_titles}
          onChange={editor.setJobTitles}
          placeholder="Add a role title"
          ariaLabel="Job titles"
        />
      </SectionShell>

      {error && <p className={styles.error}>{error}</p>}

      <div className={styles.actions}>
        <button
          className={styles.textButton}
          type="button"
          onClick={onCancel}
          disabled={submitting}
        >
          Discard changes
        </button>
        <button className="primary-action" type="button" onClick={onSave} disabled={submitting}>
          {submitting ? 'Saving…' : 'Save changes'}
        </button>
      </div>
    </div>
  );
}
