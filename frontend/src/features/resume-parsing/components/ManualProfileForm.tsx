import { useState } from 'react';

import { Alert, Button, Card } from '@shared/ui';

import { useManualProfile } from '../hooks/useManualProfile';
import { useManualProfileSubmit } from '../hooks/useManualProfileSubmit';
import type { CandidateProfile, ProfileRecord } from '../types/parsedProfile';

import { EditableProfileView } from './edit/EditableProfileView';
import styles from './ManualProfileForm.module.css';

type ManualProfileFormProps = {
  /** Fires once the profile has been saved — receives the persisted
      `ProfileRecord`, the same shape a completed parse returns. */
  onSubmit: (record: ProfileRecord) => void;
  onCancel: () => void;
  /** Starting point for the draft — e.g. a profile the person already
      filled in and came back to edit. Defaults to blank. */
  initialProfile?: CandidateProfile;
};

/**
 * Mirrors `CandidateProfile.has_usable_signal()` on the backend (see
 * `resume_parsing/schemas.py`) so an empty submission is caught here —
 * with a message the person can act on — instead of round-tripping to the
 * server just to learn the same thing.
 */
function hasUsableSignal(profile: CandidateProfile): boolean {
  return (
    profile.job_titles.length > 0 ||
    profile.skills.length > 0 ||
    profile.experience.some((entry) => Boolean(entry.job_title)) ||
    profile.projects.some((entry) => Boolean(entry.description)) ||
    profile.education.some((entry) => Boolean(entry.degree || entry.field))
  );
}

/**
 * The manual alternative to waiting on resume parsing — same fields, same
 * editable sections (`EditableProfileView`, shared with the "Edit profile"
 * flow on an already-parsed record), just starting blank instead of
 * populated from a file.
 *
 * Submitting POSTs the finished draft to the server (`useManualProfileSubmit`)
 * and hands the caller back a real, persisted `ProfileRecord` — saved and
 * encrypted the same way a parsed resume is.
 */
export function ManualProfileForm({ onSubmit, onCancel, initialProfile }: ManualProfileFormProps) {
  const manual = useManualProfile(initialProfile);
  const submission = useManualProfileSubmit();
  const [touched, setTouched] = useState(false);

  const canSubmit = hasUsableSignal(manual.draft);

  const handleContinue = () => {
    setTouched(true);
    if (!canSubmit || submission.isSubmitting) return;
    void (async () => {
      const record = await submission.submit(manual.draft);
      if (record) onSubmit(record);
    })();
  };

  return (
    <Card
      title="Enter your details"
      description="Skip the upload and fill in your background yourself — same fields either way."
    >
      <div className={styles.form}>
        <Alert tone="info" title="Saved the same way a parsed resume is">
          These fields are encrypted and stored against your account once you continue, and
          you can delete the profile at any time. Email addresses and phone numbers are never
          collected.
        </Alert>

        <EditableProfileView draft={manual.draft} onChange={manual.updateDraft} />

        {touched && !canSubmit && (
          <Alert tone="danger" title="Add at least one detail">
            Fill in a skill, job title, a piece of experience, education, or a project before
            continuing — there needs to be something to match against.
          </Alert>
        )}

        {submission.error && <Alert tone="danger" title="Couldn't save your details">{submission.error}</Alert>}

        <div className={styles.actions}>
          <Button variant="ghost" onClick={onCancel} disabled={submission.isSubmitting}>
            Back to upload
          </Button>
          <Button variant="primary" onClick={handleContinue} disabled={submission.isSubmitting}>
            {submission.isSubmitting ? (
              'Saving…'
            ) : (
              <>Continue with these details <span aria-hidden="true">→</span></>
            )}
          </Button>
        </div>
      </div>
    </Card>
  );
}
