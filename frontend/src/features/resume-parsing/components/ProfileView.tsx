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
};

/**
 * Composition only. Each section owns its own rendering and its own empty
 * state, so this stays a readable list of what a profile contains.
 */
export function ProfileView({ record }: ProfileViewProps) {
  const { profile } = record;

  return (
    <div className={styles.view}>
      <ProfileSummaryHeader record={record} />

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
