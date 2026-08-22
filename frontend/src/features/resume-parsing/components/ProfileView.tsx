import { Button } from '@shared/ui';

import { EditableProfileView } from './edit/EditableProfileView';
import { useProfileEditor } from '../hooks/useProfileEditor';
import type { ProfileRecord } from '../types/parsedProfile';

import { NeedsReviewNotice } from './NeedsReviewNotice';
import { ProfileSummaryHeader } from './ProfileSummaryHeader';
import styles from './ProfileView.module.css';
import { CertificationsSection } from './sections/CertificationsSection';
import { ContactSection } from './sections/ContactSection';
import { EducationSection } from './sections/EducationSection';
import { ExperienceSection } from './sections/ExperienceSection';
import { JobTitlesSection } from './sections/JobTitlesSection';
import { ProjectsSection } from './sections/ProjectsSection';
import { SkillsSection } from './sections/SkillsSection';


type ProfileViewProps = {
  record: ProfileRecord;
  /** Called with the updated record once an edit is saved — typically
      `useResumeUpload`'s `setRecord`, so the rest of the page (and
      whatever runs career recommendation / job discovery next) sees the
      edited profile without a re-fetch. */
  onSaved: (record: ProfileRecord) => void;
};

/**
 * Read-only display by default; "Edit" swaps every section for its
 * editable counterpart (see ./edit/) using a working copy, and "Save"
 * PATCHes the whole profile back. Edit-mode orchestration lives here via
 * `useProfileEditor` rather than in `App.tsx`, so anywhere this component
 * is rendered gets editing for free.
 */
export function ProfileView({ record, onSaved }: ProfileViewProps) {
  const editor = useProfileEditor(record, onSaved);
  const { profile } = record;

  if (editor.isEditing && editor.draft) {
    return (
      <div className={styles.view}>
        <ProfileSummaryHeader record={record} />

        <div className={styles.editBar}>
          <p className={styles.editHint}>Editing — changes apply once you save.</p>
          <div className={styles.editActions}>
            <Button variant="ghost" size="sm" onClick={editor.cancelEditing} disabled={editor.isSaving}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" onClick={() => void editor.save()} disabled={editor.isSaving}>
              {editor.isSaving ? 'Saving…' : 'Save changes'}
            </Button>
          </div>
        </div>

        {editor.error && <div className={styles.editError}>{editor.error}</div>}

        <EditableProfileView draft={editor.draft} onChange={editor.updateDraft} />
      </div>
    );
  }

  return (
    <div className={styles.view}>
      <ProfileSummaryHeader record={record} />

      <div className={styles.editBar}>
        <span />
        <Button variant="secondary" size="sm" onClick={editor.startEditing}>
          Edit profile
        </Button>
      </div>

      {(record.needs_review.length > 0 || !record.is_valid) && (
        <div className={styles.notice}>
          <NeedsReviewNotice fields={record.needs_review} isValid={record.is_valid} />
        </div>
      )}

      <ContactSection contact={profile.contact} />
      <SkillsSection skills={profile.skills} />
      <ExperienceSection experience={profile.experience} />
      <EducationSection education={profile.education} />
      <ProjectsSection projects={profile.projects} />
      <CertificationsSection certifications={profile.certifications} />
      <JobTitlesSection jobTitles={profile.job_titles} />
    </div>
  );
}
