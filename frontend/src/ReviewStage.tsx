import {
  EditProfileForm,
  ProfileView,
  useProfileEditing,
  type ProfileRecord,
} from '@features/resume-parsing';

import styles from './App.module.css';

type ReviewStageProps = {
  record: ProfileRecord;
  cvLoading: boolean;
  cvError: string | null;
  onRunCvReview: () => void;
  onRunReport: () => void;
  onReset: () => void;
  /** Fired after a successful save, so the caller can update its copy of the record. */
  onProfileSaved: (record: ProfileRecord) => void;
};

/** Step 02. The parsed profile, with both onward actions above the fold. */
export function ReviewStage({
  record,
  cvLoading,
  cvError,
  onRunCvReview,
  onRunReport,
  onReset,
  onProfileSaved,
}: ReviewStageProps) {
  const editing = useProfileEditing(record, onProfileSaved);

  return (
    <section className={styles.reviewProfile}>
      <header>
        <div>
          <p className="eyebrow">Step 02 · Review parsed resume</p>
          <h1>Check what we extracted before analysis.</h1>
          <p>
            {editing.isEditing
              ? 'Fix anything the parser missed or got wrong — this is what the rest of the pipeline will see.'
              : 'Career guidance will use exactly this profile.'}
          </p>
        </div>
        {/* Edit sits first: fixing the data should be the first thing offered,
            before critiquing it or moving on. Hidden while editing so there
            is only one thing to do at a time. */}
        {!editing.isEditing && (
          <div className={styles.headerActions}>
            <button className={styles.secondaryAction} type="button" onClick={editing.start}>
              Edit this profile
            </button>
            <button
              className={styles.secondaryAction}
              type="button"
              onClick={onRunCvReview}
              disabled={cvLoading}
            >
              {cvLoading ? 'Checking…' : 'Get ATS Score'}
            </button>
            <button className="primary-action" type="button" onClick={onRunReport}>
              Get Analysis <span aria-hidden="true">→</span>
            </button>
          </div>
        )}
      </header>

      {cvError && <div className={styles.error}>{cvError}</div>}

      {editing.isEditing ? (
        <EditProfileForm
          editor={editing.editor}
          error={editing.error}
          submitting={editing.saving}
          onSave={() => void editing.save()}
          onCancel={editing.cancel}
        />
      ) : (
        <ProfileView record={record} />
      )}

      {!editing.isEditing && (
        <footer>
          <button className={styles.textButton} type="button" onClick={onReset}>
            Use another resume
          </button>
          <button className="primary-action" type="button" onClick={onRunReport}>
            Get Analysis <span aria-hidden="true">→</span>
          </button>
        </footer>
      )}
    </section>
  );
}
