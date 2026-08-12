import { ProfileView, type ProfileRecord } from '@features/resume-parsing';

import styles from './App.module.css';

type ReviewStageProps = {
  record: ProfileRecord;
  cvLoading: boolean;
  cvError: string | null;
  onRunCvReview: () => void;
  onRunReport: () => void;
  onReset: () => void;
};

/** Step 02. The parsed profile, with both onward actions above the fold. */
export function ReviewStage({
  record,
  cvLoading,
  cvError,
  onRunCvReview,
  onRunReport,
  onReset,
}: ReviewStageProps) {
  return (
    <section className={styles.reviewProfile}>
      <header>
        <div>
          <p className="eyebrow">Step 02 · Review parsed resume</p>
          <h1>Check what we extracted before analysis.</h1>
          <p>Career guidance will use exactly this profile.</p>
        </div>
        {/* Both actions live together at the top: one critiques the CV,
            one moves forward. Pairing them makes the review a visible
            option rather than something buried below the fold. */}
        <div className={styles.headerActions}>
          <button
            className={styles.secondaryAction}
            type="button"
            onClick={onRunCvReview}
            disabled={cvLoading}
          >
            {cvLoading ? 'Checking…' : 'Major Mistakes in CV'}
          </button>
          <button className="primary-action" type="button" onClick={onRunReport}>
            Get Analysis <span aria-hidden="true">→</span>
          </button>
        </div>
      </header>

      {cvError && <div className={styles.error}>{cvError}</div>}

      <ProfileView record={record} />

      <footer>
        <button className={styles.textButton} type="button" onClick={onReset}>
          Use another resume
        </button>
        <button className="primary-action" type="button" onClick={onRunReport}>
          Get Analysis <span aria-hidden="true">→</span>
        </button>
      </footer>
    </section>
  );
}
