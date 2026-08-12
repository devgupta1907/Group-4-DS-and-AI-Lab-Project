import type { CvReview } from '@features/career-guidance';

import styles from './App.module.css';

/**
 * Critical findings only.
 *
 * The full review carries important and minor items too, but a list of a dozen
 * things to fix is not actionable. What gets a resume rejected at screening is
 * the useful subset, so that is what is shown.
 */
export function CvReviewDialog({ review, onClose }: { review: CvReview; onClose: () => void }) {
  const critical = review.findings.filter((f) => f.severity === 'critical');

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-labelledby="cv-title">
      <div className={styles.dialogWide}>
        {/* No score. A bare number out of 100 carried no scale, no basis and
            no comparison, so it invited a question the feature could not
            answer. The findings are the substance. */}
        <header className={styles.cvHead}>
          <p className="eyebrow">Major mistakes in your CV</p>
          <h2 id="cv-title">{critical.length > 0
            ? `${critical.length} thing${critical.length === 1 ? '' : 's'} to fix first`
            : 'Nothing major found'}</h2>
          <p className={styles.cvOverall}>{review.overall}</p>
        </header>

        {critical.length === 0 && (
          <p className={styles.dialogNote}>
            Nothing here would get your resume rejected at screening. Smaller
            improvements appear in the full report.
          </p>
        )}

        <ul className={styles.findings}>
          {critical.map((finding, index) => (
            <li key={`${finding.area}-${index}`}>
              <span className={styles.findingArea}>{finding.area}</span>
              <p className={styles.findingIssue}>{finding.issue}</p>
              {finding.evidence && (
                <p className={styles.findingEvidence}>&ldquo;{finding.evidence}&rdquo;</p>
              )}
              <p className={styles.findingFix}><b>Fix:</b> {finding.fix}</p>
            </li>
          ))}
        </ul>

        <div className={styles.dialogActions}>
          <span />
          <button className="primary-action" type="button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
